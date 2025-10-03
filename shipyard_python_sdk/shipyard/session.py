"""
Shipyard Python SDK - Session ship implementation
"""

import uuid
import filetype
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

    async def upload_file(
        self, file_content: bytes, remote_file_path: str | None = None
    ) -> Dict[str, Any]:
        """Upload file to this ship session

        Args:
            file_content: File content as bytes
            file_path: Path where the file should be saved in the ship workspace, if None, a unique path will be generated

        Returns:
            Dictionary with upload result information
        """
        uuid_str = str(uuid.uuid4())

        if not remote_file_path:
            kind = filetype.guess(file_content)
            ext = f".{kind.extension}" if kind else ""
            remote_file_path = f"{uuid_str}_uploaded_file{ext}"

        return await self._client.upload_file(
            self.id, remote_file_path, file_content, self._session_id
        )
