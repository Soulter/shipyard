import asyncio
import os
import signal
from typing import Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from pathlib import Path

router = APIRouter()

# 存储正在运行的进程，按 session_id 分组
running_processes: Dict[str, Dict[str, asyncio.subprocess.Process]] = {}

# 工作目录根路径
WORKSPACE_ROOT = Path("workspace")
WORKSPACE_ROOT.mkdir(exist_ok=True)


def get_session_workspace(session_id: str) -> Path:
    """获取 session 的工作目录"""
    workspace_dir = WORKSPACE_ROOT / session_id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


def get_session_processes(session_id: str) -> Dict[str, asyncio.subprocess.Process]:
    """获取 session 的进程字典"""
    if session_id not in running_processes:
        running_processes[session_id] = {}
    return running_processes[session_id]


class ExecuteShellRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    timeout: Optional[int] = 30
    shell: bool = True
    background: bool = False


class ExecuteShellResponse(BaseModel):
    success: bool
    return_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    pid: Optional[int] = None
    process_id: Optional[str] = None  # 用于后台进程
    error: Optional[str] = None


class ProcessInfo(BaseModel):
    process_id: str
    pid: int
    command: str
    status: str


def generate_process_id() -> str:
    """生成进程ID"""
    import uuid

    return str(uuid.uuid4())[:8]


async def run_command(
    session_id: str,
    command: str,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
    shell: bool = True,
    background: bool = False,
) -> Dict[str, Any]:
    """执行shell命令"""

    # 准备环境变量
    process_env = os.environ.copy()
    if env:
        process_env.update(env)

    # 准备工作目录。如果未指定，使用 session 工作目录
    if cwd is None:
        working_dir = get_session_workspace(session_id)
    else:
        # 相对路径相对于 session 工作目录解析
        if not os.path.isabs(cwd):
            working_dir = get_session_workspace(session_id) / cwd
        else:
            working_dir = Path(cwd)

    if not working_dir.exists():
        raise ValueError(f"Working directory does not exist: {working_dir}")

    session_processes = get_session_processes(session_id)

    try:
        if shell:
            # 使用shell模式
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir),
                env=process_env,
            )
        else:
            # 分割命令参数
            args = command.split()
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir),
                env=process_env,
            )

        if background:
            # 后台进程
            process_id = generate_process_id()
            session_processes[process_id] = process

            return {
                "success": True,
                "pid": process.pid,
                "process_id": process_id,
                "return_code": None,
                "stdout": "",
                "stderr": "",
                "error": None,
            }
        else:
            # 前台进程，等待完成
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )

                return {
                    "success": process.returncode == 0,
                    "return_code": process.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "pid": process.pid,
                    "process_id": None,
                    "error": None,
                }

            except asyncio.TimeoutError:
                # 超时，终止进程
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

                return {
                    "success": False,
                    "return_code": -signal.SIGTERM,
                    "stdout": "",
                    "stderr": "",
                    "pid": process.pid,
                    "process_id": None,
                    "error": f"Command timed out after {timeout} seconds",
                }

    except Exception as e:
        return {
            "success": False,
            "return_code": None,
            "stdout": "",
            "stderr": "",
            "pid": None,
            "process_id": None,
            "error": str(e),
        }


@router.post("/exec", response_model=ExecuteShellResponse)
async def execute_shell_command(
    request: ExecuteShellRequest, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """执行Shell命令"""
    try:
        result = await run_command(
            session_id=x_session_id,
            command=request.command,
            cwd=request.cwd,
            env=request.env,
            timeout=request.timeout,
            shell=request.shell,
            background=request.background,
        )

        return ExecuteShellResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to execute command: {str(e)}"
        )


@router.get("/processes")
async def list_processes(x_session_id: str = Header(..., alias="X-SESSION-ID")):
    """列出指定 session 正在运行的后台进程"""
    try:
        session_processes = get_session_processes(x_session_id)
        processes = []
        to_remove = []

        for process_id, process in session_processes.items():
            try:
                if process.returncode is None:
                    # 进程仍在运行
                    status = "running"
                else:
                    # 进程已结束
                    status = f"finished (code: {process.returncode})"
                    to_remove.append(process_id)

                processes.append(
                    ProcessInfo(
                        process_id=process_id,
                        pid=process.pid,
                        command="",  # 暂时不存储原始命令
                        status=status,
                    )
                )
            except Exception:
                # 进程可能已经不存在
                to_remove.append(process_id)

        # 清理已结束的进程
        for process_id in to_remove:
            del session_processes[process_id]

        return {"processes": processes}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list processes: {str(e)}"
        )


@router.get("/process/{process_id}")
async def get_process_status(
    process_id: str, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """获取指定进程的状态"""
    try:
        session_processes = get_session_processes(x_session_id)
        if process_id not in session_processes:
            raise HTTPException(
                status_code=404, detail=f"Process {process_id} not found"
            )

        process = session_processes[process_id]

        if process.returncode is None:
            status = "running"
        else:
            status = f"finished (code: {process.returncode})"

        return {
            "process_id": process_id,
            "pid": process.pid,
            "status": status,
            "return_code": process.returncode,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get process status: {str(e)}"
        )


@router.delete("/process/{process_id}")
async def terminate_process(
    process_id: str, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """终止指定的后台进程"""
    try:
        session_processes = get_session_processes(x_session_id)
        if process_id not in session_processes:
            raise HTTPException(
                status_code=404, detail=f"Process {process_id} not found"
            )

        process = session_processes[process_id]

        if process.returncode is None:
            # 进程仍在运行，尝试终止
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                # 强制杀死
                process.kill()
                await process.wait()

        del session_processes[process_id]

        return {
            "success": True,
            "message": f"Process {process_id} terminated successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to terminate process: {str(e)}"
        )


@router.post("/process/{process_id}/output")
async def get_process_output(
    process_id: str, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """获取后台进程的输出（如果有的话）"""
    try:
        session_processes = get_session_processes(x_session_id)
        if process_id not in session_processes:
            raise HTTPException(
                status_code=404, detail=f"Process {process_id} not found"
            )

        process = session_processes[process_id]

        # 注意：对于后台进程，我们通常不能获取实时输出
        # 这里提供一个基本的实现，实际使用中可能需要更复杂的日志管理

        return {
            "process_id": process_id,
            "pid": process.pid,
            "status": "running"
            if process.returncode is None
            else f"finished (code: {process.returncode})",
            "return_code": process.returncode,
            "note": "Real-time output capture for background processes is not implemented yet",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get process output: {str(e)}"
        )


@router.get("/cwd")
async def get_current_directory(x_session_id: str = Header(..., alias="X-SESSION-ID")):
    """获取指定 session 的当前工作目录"""
    try:
        workspace_dir = get_session_workspace(x_session_id)
        return {"cwd": str(workspace_dir.absolute()), "exists": True}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get current directory: {str(e)}"
        )
