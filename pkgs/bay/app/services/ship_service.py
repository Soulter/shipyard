import aiohttp
import asyncio
import logging
from typing import Optional, List
from app.config import settings
from app.models import Ship, CreateShipRequest, ExecRequest, ExecResponse
from app.database import db_service
from app.services.docker_service import docker_service

logger = logging.getLogger(__name__)


class ShipService:
    """Service for managing Ship lifecycle and operations"""

    async def create_ship(self, request: CreateShipRequest) -> Ship:
        """Create a new ship"""
        # Check ship limits
        if settings.behavior_after_max_ship == "reject":
            active_count = await db_service.count_active_ships()
            if active_count >= settings.max_ship_num:
                raise ValueError("Maximum number of ships reached")
        elif settings.behavior_after_max_ship == "wait":
            # Wait for available slot
            await self._wait_for_available_slot()

        # Create ship record
        ship = Ship(ttl=request.ttl)
        ship = await db_service.create_ship(ship)

        try:
            # Create container
            container_info = await docker_service.create_ship_container(
                ship, request.spec
            )

            # Update ship with container info
            ship.container_id = container_info["container_id"]
            ship.ip_address = container_info["ip_address"]
            ship = await db_service.update_ship(ship)

            # Schedule TTL cleanup
            asyncio.create_task(self._schedule_cleanup(ship.id, ship.ttl))

            return ship

        except Exception as e:
            # Cleanup on failure
            await db_service.delete_ship(ship.id)
            logger.error(f"Failed to create ship {ship.id}: {e}")
            raise

    async def get_ship(self, ship_id: str) -> Optional[Ship]:
        """Get ship by ID"""
        return await db_service.get_ship(ship_id)

    async def delete_ship(self, ship_id: str) -> bool:
        """Delete ship"""
        ship = await db_service.get_ship(ship_id)
        if not ship:
            return False

        # Stop container if exists
        if ship.container_id:
            try:
                await docker_service.stop_ship_container(ship.container_id)
            except Exception as e:
                logger.error(f"Failed to stop container for ship {ship_id}: {e}")

        # Delete from database
        return await db_service.delete_ship(ship_id)

    async def extend_ttl(self, ship_id: str, new_ttl: int) -> Optional[Ship]:
        """Extend ship TTL"""
        ship = await db_service.get_ship(ship_id)
        if not ship or ship.status == 0:
            return None

        ship.ttl = new_ttl
        ship = await db_service.update_ship(ship)

        # Reschedule cleanup
        asyncio.create_task(self._schedule_cleanup(ship_id, new_ttl))

        return ship

    async def execute_operation(
        self, ship_id: str, request: ExecRequest
    ) -> ExecResponse:
        """Execute operation on ship"""
        ship = await db_service.get_ship(ship_id)
        if not ship or ship.status == 0:
            return ExecResponse(success=False, error="Ship not found or not running")

        if not ship.ip_address:
            return ExecResponse(success=False, error="Ship IP address not available")

        # Forward request to ship container
        return await self._forward_to_ship(ship.ip_address, request)

    async def get_logs(self, ship_id: str) -> str:
        """Get ship container logs"""
        ship = await db_service.get_ship(ship_id)
        if not ship or not ship.container_id:
            return ""

        return await docker_service.get_container_logs(ship.container_id)

    async def list_active_ships(self) -> List[Ship]:
        """List all active ships"""
        return await db_service.list_active_ships()

    async def _wait_for_available_slot(self):
        """Wait for an available ship slot"""
        max_wait_time = 300  # 5 minutes
        check_interval = 5  # 5 seconds
        waited = 0

        while waited < max_wait_time:
            active_count = await db_service.count_active_ships()
            if active_count < settings.max_ship_num:
                return

            await asyncio.sleep(check_interval)
            waited += check_interval

        raise TimeoutError("Timeout waiting for available ship slot")

    async def _schedule_cleanup(self, ship_id: str, ttl: int):
        """Schedule ship cleanup after TTL expires"""
        await asyncio.sleep(ttl)

        try:
            ship = await db_service.get_ship(ship_id)
            if ship and ship.status == 1:
                # Mark as stopped
                ship.status = 0
                await db_service.update_ship(ship)

                # Stop container
                if ship.container_id:
                    await docker_service.stop_ship_container(ship.container_id)

                logger.info(f"Ship {ship_id} cleaned up after TTL expiration")
        except Exception as e:
            logger.error(f"Failed to cleanup ship {ship_id}: {e}")

    async def _forward_to_ship(
        self, ship_ip: str, request: ExecRequest
    ) -> ExecResponse:
        """Forward request to ship container"""
        url = f"http://{ship_ip}:8080/{request.type}"

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=request.payload or {}) as response:
                    if response.status == 200:
                        data = await response.json()
                        return ExecResponse(success=True, data=data)
                    else:
                        error_text = await response.text()
                        return ExecResponse(
                            success=False,
                            error=f"Ship returned {response.status}: {error_text}",
                        )

        except aiohttp.ClientError as e:
            logger.error(f"Failed to forward request to ship {ship_ip}: {e}")
            return ExecResponse(success=False, error=f"Connection error: {str(e)}")
        except asyncio.TimeoutError:
            return ExecResponse(success=False, error="Request timeout")
        except Exception as e:
            logger.error(f"Unexpected error forwarding to ship {ship_ip}: {e}")
            return ExecResponse(success=False, error=f"Internal error: {str(e)}")


# Global ship service instance
ship_service = ShipService()
