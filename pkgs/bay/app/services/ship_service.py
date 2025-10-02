import aiohttp
import asyncio
import logging
from typing import Optional, List
from app.config import settings
from app.models import Ship, CreateShipRequest, ExecRequest, ExecResponse, SessionShip
from app.database import db_service
from app.services.docker_service import docker_service

logger = logging.getLogger(__name__)


class ShipService:
    """Service for managing Ship lifecycle and operations"""

    async def create_ship(self, request: CreateShipRequest, session_id: str) -> Ship:
        """Create a new ship or reuse an existing one for the session"""
        # First, try to find an available ship that can accept this session
        available_ship = await db_service.find_available_ship(session_id)

        if available_ship:
            # Check if this session already has access to this ship
            existing_session = await db_service.get_session_ship(
                session_id, available_ship.id
            )

            if existing_session:
                # Update last activity and return existing ship
                await db_service.update_session_activity(session_id, available_ship.id)
                return available_ship
            else:
                # Add this session to the ship
                session_ship = SessionShip(
                    session_id=session_id, ship_id=available_ship.id
                )
                await db_service.create_session_ship(session_ship)
                await db_service.increment_ship_session_count(available_ship.id)
                return available_ship

        # No available ship found, create a new one
        # Check ship limits
        if settings.behavior_after_max_ship == "reject":
            active_count = await db_service.count_active_ships()
            if active_count >= settings.max_ship_num:
                raise ValueError("Maximum number of ships reached")
        elif settings.behavior_after_max_ship == "wait":
            # Wait for available slot
            await self._wait_for_available_slot()

        # Create ship record
        ship = Ship(ttl=request.ttl, max_session_num=request.max_session_num)
        ship = await db_service.create_ship(ship)

        try:
            # Create container
            container_info = await docker_service.create_ship_container(
                ship, request.spec
            )

            # Update ship with container info
            ship.container_id = container_info["container_id"]
            ship.ip_address = container_info["ip_address"]
            ship.current_session_num = 1  # First session
            ship = await db_service.update_ship(ship)

            # Wait for ship to be ready
            if not ship.ip_address:
                logger.error(f"Ship {ship.id} has no IP address")
                await db_service.delete_ship(ship.id)
                raise RuntimeError("Ship has no IP address")

            logger.info(f"Waiting for ship {ship.id} to become ready...")
            is_ready = await self._wait_for_ship_ready(ship.ip_address)

            if not is_ready:
                # Ship failed to become ready, cleanup
                logger.error(f"Ship {ship.id} failed health check, cleaning up")
                if ship.container_id:
                    await docker_service.stop_ship_container(ship.container_id)
                await db_service.delete_ship(ship.id)
                raise RuntimeError(
                    f"Ship failed to become ready within {settings.ship_health_check_timeout} seconds"
                )

            # Create session-ship relationship
            session_ship = SessionShip(session_id=session_id, ship_id=ship.id)
            await db_service.create_session_ship(session_ship)
            await db_service.increment_ship_session_count(ship.id)

            # Schedule TTL cleanup
            asyncio.create_task(self._schedule_cleanup(ship.id, ship.ttl))

            logger.info(f"Ship {ship.id} created successfully and is ready")
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
        self, ship_id: str, request: ExecRequest, session_id: str
    ) -> ExecResponse:
        """Execute operation on ship"""
        ship = await db_service.get_ship(ship_id)
        if not ship or ship.status == 0:
            return ExecResponse(success=False, error="Ship not found or not running")

        if not ship.ip_address:
            return ExecResponse(success=False, error="Ship IP address not available")

        # Verify that this session has access to this ship
        session_ship = await db_service.get_session_ship(session_id, ship_id)
        if not session_ship:
            return ExecResponse(
                success=False, error="Session does not have access to this ship"
            )

        # Update last activity for this session
        await db_service.update_session_activity(session_id, ship_id)

        # Forward request to ship container
        return await self._forward_to_ship(ship.ip_address, request, session_id)

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
        self, ship_ip: str, request: ExecRequest, session_id: str
    ) -> ExecResponse:
        """Forward request to ship container"""
        url = f"http://{ship_ip}:8123/{request.type}"

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            headers = {"X-SESSION-ID": session_id}
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url, json=request.payload or {}, headers=headers
                ) as response:
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

    async def _wait_for_ship_ready(self, ship_ip: str) -> bool:
        """Wait for ship to be ready by polling /health endpoint"""
        health_url = f"http://{ship_ip}:8123/health"
        max_wait_time = settings.ship_health_check_timeout
        check_interval = settings.ship_health_check_interval
        waited = 0

        logger.info(f"Starting health check for ship at {ship_ip}")

        while waited < max_wait_time:
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(health_url) as response:
                        if response.status == 200:
                            logger.info(f"Ship at {ship_ip} is ready after {waited}s")
                            return True
            except Exception as e:
                logger.debug(f"Health check failed for {ship_ip}: {e}")

            await asyncio.sleep(check_interval)
            waited += check_interval

        logger.error(
            f"Ship at {ship_ip} failed to become ready within {max_wait_time}s"
        )
        return False


# Global ship service instance
ship_service = ShipService()
