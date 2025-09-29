import aiodocker
from aiodocker.exceptions import DockerError
from typing import Optional, Dict, Any
from app.config import settings
from app.models import Ship, ShipSpec
import logging

logger = logging.getLogger(__name__)


class DockerService:
    def __init__(self):
        self.client: Optional[aiodocker.Docker] = None

    async def initialize(self):
        """Initialize Docker client"""
        try:
            self.client = aiodocker.Docker()
            # Test connection
            await self.client.version()
            logger.info("Docker client initialized successfully")
        except DockerError as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise

    async def close(self):
        """Close Docker client"""
        if self.client:
            await self.client.close()

    async def create_ship_container(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> Dict[str, Any]:
        """Create and start a ship container"""
        if not self.client:
            await self.initialize()

        assert self.client is not None  # For type checker

        container_config = self._build_container_config(ship, spec)

        try:
            # Create container
            container = await self.client.containers.create_or_replace(
                name=container_config["name"], config=container_config["config"]
            )

            # Start container
            await container.start()

            # Get container info
            container_info = await container.show()

            # Get container IP address
            ip_address = None
            network_settings = container_info.get("NetworkSettings", {})

            if (
                settings.docker_network
                and settings.docker_network in network_settings.get("Networks", {})
            ):
                ip_address = network_settings["Networks"][settings.docker_network].get(
                    "IPAddress"
                )
            else:
                ip_address = network_settings.get("IPAddress")

            return {
                "container_id": container.id,
                "ip_address": ip_address,
                "status": container_info.get("State", {}).get("Status", "unknown"),
            }

        except DockerError as e:
            logger.error(f"Failed to create container for ship {ship.id}: {e}")
            raise

    async def stop_ship_container(self, container_id: str) -> bool:
        """Stop and remove ship container"""
        if not self.client:
            await self.initialize()

        assert self.client is not None  # For type checker

        try:
            # Get container
            container = await self.client.containers.get(container_id)

            # Stop container
            await container.stop()

            # Remove container
            await container.delete()

            return True

        except DockerError as e:
            if "No such container" in str(e):
                logger.warning(f"Container {container_id} not found")
                return True  # Already removed
            logger.error(f"Failed to stop container {container_id}: {e}")
            return False

    async def get_container_logs(self, container_id: str) -> str:
        """Get container logs"""
        if not self.client:
            await self.initialize()

        assert self.client is not None  # For type checker

        try:
            # Get container
            container = await self.client.containers.get(container_id)

            # Get logs
            logs_stream = await container.log(stdout=True, stderr=True)
            logs = "".join([line for line in logs_stream])

            return logs

        except DockerError as e:
            if "No such container" in str(e):
                logger.warning(f"Container {container_id} not found")
                return ""
            logger.error(f"Failed to get logs for container {container_id}: {e}")
            return ""

    async def is_container_running(self, container_id: str) -> bool:
        """Check if container is running"""
        if not self.client:
            await self.initialize()

        assert self.client is not None  # For type checker

        try:
            # Get container
            container = await self.client.containers.get(container_id)

            # Get container info
            container_info = await container.show()
            return container_info.get("State", {}).get("Status") == "running"

        except DockerError as e:
            if "No such container" in str(e):
                return False
            logger.error(f"Failed to check container {container_id} status: {e}")
            return False

    def _build_container_config(
        self, ship: Ship, spec: Optional[ShipSpec] = None
    ) -> Dict[str, Any]:
        """Build container configuration for aiodocker"""
        # Host configuration for resource limits
        host_config = {
            "RestartPolicy": {"Name": "no"},
            "PortBindings": {
                "8123/tcp": [{"HostPort": ""}]  # Let Docker assign random port
            },
        }

        # Apply spec if provided
        if spec:
            if spec.cpus:
                host_config["CpuQuota"] = int(spec.cpus * 100000)
                host_config["CpuPeriod"] = 100000

            if spec.memory:
                host_config["Memory"] = self._parse_memory_string(spec.memory)

        # Container configuration
        config = {
            "Image": settings.docker_image,
            "Env": [f"SHIP_ID={ship.id}", f"TTL={ship.ttl}"],
            "Labels": {"ship_id": ship.id, "created_by": "bay"},
            "ExposedPorts": {"8123/tcp": {}},
            "HostConfig": host_config,
        }

        # Add network if configured
        if settings.docker_network:
            config["NetworkingConfig"] = {
                "EndpointsConfig": {settings.docker_network: {}}
            }

        return {"name": f"ship-{ship.id}", "config": config}

    def _parse_memory_string(self, memory_str: str) -> int:
        """Parse memory string (e.g., '512m', '1g') to bytes"""
        memory_str = memory_str.lower().strip()

        if memory_str.endswith("k") or memory_str.endswith("kb"):
            return (
                int(memory_str[:-1] if memory_str.endswith("k") else memory_str[:-2])
                * 1024
            )
        elif memory_str.endswith("m") or memory_str.endswith("mb"):
            return (
                int(memory_str[:-1] if memory_str.endswith("m") else memory_str[:-2])
                * 1024
                * 1024
            )
        elif memory_str.endswith("g") or memory_str.endswith("gb"):
            return (
                int(memory_str[:-1] if memory_str.endswith("g") else memory_str[:-2])
                * 1024
                * 1024
                * 1024
            )
        else:
            # Assume bytes if no suffix
            return int(memory_str)


# Global docker service instance
docker_service = DockerService()
