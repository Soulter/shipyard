import os
import aiofiles
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

router = APIRouter()

# 工作目录根路径
WORKSPACE_ROOT = Path("workspace")
WORKSPACE_ROOT.mkdir(exist_ok=True)


def get_session_workspace(session_id: str) -> Path:
    """获取 session 的工作目录"""
    workspace_dir = WORKSPACE_ROOT / session_id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


def resolve_path(session_id: str, path: str) -> Path:
    """解析相对于 session 工作目录的路径"""
    workspace_dir = get_session_workspace(session_id)

    # 如果是绝对路径，检查是否在工作目录内
    if os.path.isabs(path):
        abs_path = Path(path)
        # 确保路径在工作目录内
        try:
            abs_path.resolve().relative_to(workspace_dir.resolve())
            return abs_path
        except ValueError:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: path must be within workspace {workspace_dir}",
            )
    else:
        # 相对路径，相对于工作目录
        return workspace_dir / path


# 定义请求和响应模型
class CreateFileRequest(BaseModel):
    path: str
    content: str = ""
    mode: int = 0o644


class ReadFileRequest(BaseModel):
    path: str
    encoding: str = "utf-8"
    offset: Optional[int] = None  # 起始行号（1-based），None 表示从头开始
    limit: Optional[int] = None  # 最大读取行数，None 表示读取所有行


class WriteFileRequest(BaseModel):
    path: str
    content: str
    mode: str = "w"  # "w" for write, "a" for append
    encoding: str = "utf-8"


class DeleteFileRequest(BaseModel):
    path: str


class ListDirRequest(BaseModel):
    path: str = "."
    show_hidden: bool = False


class FileInfo(BaseModel):
    name: str
    path: str
    is_file: bool
    is_dir: bool
    size: Optional[int] = None
    modified_time: Optional[float] = None


class ListDirResponse(BaseModel):
    files: List[FileInfo]
    current_path: str


class FileResponse(BaseModel):
    content: str
    path: str
    size: int


@router.post("/create_file")
async def create_file(
    request: CreateFileRequest, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """创建文件"""
    try:
        file_path = resolve_path(x_session_id, request.path)

        # 确保父目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建文件
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(request.content)

        # 设置文件权限
        os.chmod(file_path, request.mode)

        return {
            "success": True,
            "message": f"File created: {request.path}",
            "path": str(file_path.absolute()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create file: {str(e)}")


@router.post("/read_file", response_model=FileResponse)
async def read_file(
    request: ReadFileRequest, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """读取文件内容"""
    try:
        file_path = resolve_path(x_session_id, request.path)

        if not file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"File not found: {request.path}"
            )

        if not file_path.is_file():
            raise HTTPException(
                status_code=400, detail=f"Path is not a file: {request.path}"
            )

        async with aiofiles.open(file_path, "r", encoding=request.encoding) as f:
            lines = await f.readlines()
            offset = request.offset if request.offset is not None else 1
            limit = request.limit if request.limit is not None else len(lines)
            start_index = max(0, offset - 1) if offset > 0 else 0
            if start_index >= len(lines):
                content = ""
            else:
                end_index = start_index + limit
                content = "".join(lines[start_index:end_index])

        stat = file_path.stat()
        return FileResponse(
            content=content, path=str(file_path.absolute()), size=stat.st_size
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.post("/write_file")
async def write_file(
    request: WriteFileRequest, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """写入文件内容"""
    try:
        file_path = resolve_path(x_session_id, request.path)

        # 确保父目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 确保模式是合法的
        mode = "w" if request.mode == "w" else "a"

        async with aiofiles.open(file_path, mode, encoding=request.encoding) as f:
            await f.write(request.content)

        stat = file_path.stat()
        return {
            "success": True,
            "message": f"File written: {request.path}",
            "path": str(file_path.absolute()),
            "size": stat.st_size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")


@router.post("/delete_file")
async def delete_file(
    request: DeleteFileRequest, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """删除文件或目录"""
    try:
        file_path = resolve_path(x_session_id, request.path)

        if not file_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Path not found: {request.path}"
            )

        if file_path.is_file():
            file_path.unlink()
            return {"success": True, "message": f"File deleted: {request.path}"}
        elif file_path.is_dir():
            # 递归删除目录
            import shutil

            shutil.rmtree(file_path)
            return {"success": True, "message": f"Directory deleted: {request.path}"}
        else:
            raise HTTPException(
                status_code=400, detail=f"Unknown path type: {request.path}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")


@router.post("/list_dir", response_model=ListDirResponse)
async def list_directory(
    request: ListDirRequest, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """列出目录内容"""
    try:
        dir_path = resolve_path(x_session_id, request.path)

        if not dir_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Directory not found: {request.path}"
            )

        if not dir_path.is_dir():
            raise HTTPException(
                status_code=400, detail=f"Path is not a directory: {request.path}"
            )

        files = []
        for item in dir_path.iterdir():
            # 跳过隐藏文件（除非明确要求显示）
            if not request.show_hidden and item.name.startswith("."):
                continue

            try:
                stat = item.stat()
                file_info = FileInfo(
                    name=item.name,
                    path=str(item.absolute()),
                    is_file=item.is_file(),
                    is_dir=item.is_dir(),
                    size=stat.st_size if item.is_file() else None,
                    modified_time=stat.st_mtime,
                )
                files.append(file_info)
            except (OSError, PermissionError):
                # 跳过无法访问的文件
                continue

        # 排序：目录在前，然后按名称排序
        files.sort(key=lambda x: (not x.is_dir, x.name.lower()))

        return ListDirResponse(files=files, current_path=str(dir_path.absolute()))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list directory: {str(e)}"
        )
