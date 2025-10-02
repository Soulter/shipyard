"""
Shipyard Python SDK - File system component
"""

from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import ShipyardClient


class FileSystemComponent:
    """File system operations component"""

    def __init__(self, client: "ShipyardClient", ship_id: str, session_id: str):
        self._client = client
        self._ship_id = ship_id
        self._session_id = session_id

    async def create_file(
        self, path: str, content: str = "", mode: int = 0o644
    ) -> Dict[str, Any]:
        """Create a file with the specified content"""
        payload = {"path": path, "content": content, "mode": mode}
        return await self._client._exec_operation(
            self._ship_id, "fs/create_file", payload, self._session_id
        )

    async def read_file(self, path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read file content"""
        payload = {"path": path, "encoding": encoding}
        return await self._client._exec_operation(
            self._ship_id, "fs/read_file", payload, self._session_id
        )

    async def write_file(
        self, path: str, content: str, mode: str = "w", encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """Write content to file"""
        payload = {"path": path, "content": content, "mode": mode, "encoding": encoding}
        return await self._client._exec_operation(
            self._ship_id, "fs/write_file", payload, self._session_id
        )

    async def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete file or directory"""
        payload = {"path": path}
        return await self._client._exec_operation(
            self._ship_id, "fs/delete_file", payload, self._session_id
        )

    async def list_dir(
        self, path: str = ".", show_hidden: bool = False
    ) -> Dict[str, Any]:
        """List directory contents"""
        payload = {"path": path, "show_hidden": show_hidden}
        return await self._client._exec_operation(
            self._ship_id, "fs/list_dir", payload, self._session_id
        )
