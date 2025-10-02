"""
Shipyard Python SDK - Session ship implementation
"""

from typing import Dict, Any, TYPE_CHECKING
from .types import ShipInfo
from .filesystem import FileSystemComponent
from .shell import ShellComponent
from .python import PythonComponent

if TYPE_CHECKING:
    from .client import ShipyardClient


class SessionShip(ShipInfo):
    """Represents a ship session with file system, shell, and Python components"""

    def __init__(
        self, client: "ShipyardClient", ship_data: Dict[str, Any], session_id: str
    ):
        super().__init__(ship_data)
        self._client = client
        self._session_id = session_id

        # Initialize components
        self.fs = FileSystemComponent(client, self.id, session_id)
        self.shell = ShellComponent(client, self.id, session_id)
        self.python = PythonComponent(client, self.id, session_id)

    async def extend_ttl(self, ttl: int) -> Dict[str, Any]:
        """Extend the ship's TTL"""
        return await self._client.extend_ship_ttl(self.id, ttl)

    async def get_logs(self) -> str:
        """Get ship container logs"""
        return await self._client.get_ship_logs(self.id)
