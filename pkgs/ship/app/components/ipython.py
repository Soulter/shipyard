import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from jupyter_client.manager import AsyncKernelManager

router = APIRouter()

# 全局内核管理器字典，以 session_id 为 key
kernel_managers: Dict[str, AsyncKernelManager] = {}
# 工作目录根路径
WORKSPACE_ROOT = Path("workspace")
WORKSPACE_ROOT.mkdir(exist_ok=True)


class ExecuteCodeRequest(BaseModel):
    code: str
    kernel_id: Optional[str] = None
    timeout: int = 30
    silent: bool = False


class ExecuteCodeResponse(BaseModel):
    success: bool
    execution_count: Optional[int] = None
    output: dict = {}
    error: Optional[str] = None
    kernel_id: str


class KernelInfo(BaseModel):
    kernel_id: str
    status: str
    connections: int


def get_session_workspace(session_id: str) -> Path:
    """获取 session 的工作目录"""
    workspace_dir = WORKSPACE_ROOT / session_id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


async def get_or_create_kernel(session_id: str) -> AsyncKernelManager:
    """获取或创建内核管理器，基于 session_id"""
    if session_id not in kernel_managers:
        # 创建会话工作目录
        workspace_dir = get_session_workspace(session_id)

        # 创建新的内核管理器
        km: AsyncKernelManager = AsyncKernelManager()
        await km.start_kernel()
        kernel_managers[session_id] = km

        # 在内核启动后立即设置工作目录
        await _set_kernel_working_directory(km, str(workspace_dir))

    return kernel_managers[session_id]


async def ensure_kernel_running(km: AsyncKernelManager):
    """确保内核正在运行"""
    if not km.has_kernel or not await km.is_alive():
        await km.start_kernel()


async def _set_kernel_working_directory(km: AsyncKernelManager, working_dir: str):
    """设置内核的工作目录"""
    kc = km.client()
    try:
        # 执行初始化代码，包括中文字体配置
        init_code = f"""
import os
os.chdir(r'{working_dir}')

# 配置中文字体支持
try:
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    
    # 直接指定中文字体路径
    chinese_font_paths = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    ]
    
    # 尝试添加中文字体
    font_configured = False
    for font_path in chinese_font_paths:
        try:
            import os
            if os.path.exists(font_path):
                # 添加字体到matplotlib
                fm.fontManager.addfont(font_path)
                # 获取字体名称
                font_prop = fm.FontProperties(fname=font_path)
                font_name = font_prop.get_name()
                
                # 配置matplotlib使用该字体
                plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
                plt.rcParams['axes.unicode_minus'] = False
                plt.rcParams['font.family'] = 'sans-serif'
                
                print(f"Chinese font configured: {{font_name}} from {{font_path}}")
                font_configured = True
                break
        except Exception as font_err:
            print(f"Failed to load font {{font_path}}: {{font_err}}")
            continue
    
    if not font_configured:
        # 回退到默认配置
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        print("Using default font configuration")
        
except ImportError:
    print("matplotlib not available")
except Exception as e:
    print(f"Font configuration error: {{e}}")

print(f"Working directory changed to: {{os.getcwd()}}")
"""
        kc.execute(init_code, silent=True, store_history=False)

        # 等待执行完成
        timeout = 10  # 增加超时时间以便字体配置完成
        while True:
            try:
                msg = await asyncio.wait_for(kc.get_iopub_msg(), timeout=timeout)
                if (
                    msg["msg_type"] == "status"
                    and msg["content"].get("execution_state") == "idle"
                ):
                    break
            except asyncio.TimeoutError:
                break

    except Exception as e:
        print(f"Warning: Failed to set working directory: {e}")


async def execute_code_in_kernel(
    km: AsyncKernelManager, code: str, timeout: int = 30, silent: bool = False
) -> Dict[str, Any]:
    """在内核中执行代码"""
    await ensure_kernel_running(km)

    kc = km.client()

    try:
        # 执行代码
        kc.execute(code, silent=silent, store_history=not silent)

        outputs = {
            "text": "",
            "images": [],
        }
        plains = []
        execution_count = None
        error = None

        # 等待执行完成
        while True:
            try:
                msg = await asyncio.wait_for(kc.get_iopub_msg(), timeout=timeout)
                msg_type = msg["msg_type"]
                content = msg["content"]

                if msg_type == "execute_input":
                    execution_count = content.get("execution_count")
                elif msg_type == "execute_result":
                    data = content.get("data", {})
                    if isinstance(data, dict):
                        if "text/plain" in data:
                            plains.append(data["text/plain"])
                        if "image/png" in data:
                            outputs["images"].append({"image/png": data["image/png"]})
                elif msg_type == "display_data":
                    data = content.get("data", {})
                    if isinstance(data, dict) and "image/png" in data:
                        outputs["images"].append({"image/png": data["image/png"]})
                    elif "text/plain" in data:
                        plains.append(data["text/plain"])
                elif msg_type == "stream":
                    plains.append(content.get("text", ""))
                elif msg_type == "error":
                    error = "\n".join(content.get("traceback", []))
                elif msg_type == "status" and content.get("execution_state") == "idle":
                    # 执行完成
                    break

            except asyncio.TimeoutError:
                error = f"Code execution timed out after {timeout} seconds"
                break

        outputs["text"] = "".join(plains).strip()

        return {
            "success": error is None,
            "execution_count": execution_count,
            "output": outputs,
            "error": error,
        }

    except Exception as e:
        print(f"Error during code execution: {e}")
        return {
            "success": False,
            "execution_count": None,
            "output": {},
            "error": f"Execution error: {str(e)}",
        }


@router.post("/exec", response_model=ExecuteCodeResponse)
async def execute_code(
    request: ExecuteCodeRequest, x_session_id: str = Header(..., alias="X-SESSION-ID")
):
    """执行 IPython 代码"""
    try:
        # 使用 session_id 作为 kernel_id
        session_id = x_session_id
        km = await get_or_create_kernel(session_id)

        result = await execute_code_in_kernel(
            km, request.code, timeout=request.timeout, silent=request.silent
        )

        print(result)

        return ExecuteCodeResponse(
            success=result["success"],
            execution_count=result["execution_count"],
            output=result["output"],
            error=result["error"],
            kernel_id=session_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute code: {str(e)}")


@router.post("/create_kernel")
async def create_kernel(x_session_id: str = Header(..., alias="X-SESSION-ID")):
    """为指定 session 创建新的内核"""
    try:
        session_id = x_session_id
        await get_or_create_kernel(session_id)

        return {
            "success": True,
            "kernel_id": session_id,
            "workspace": str(get_session_workspace(session_id)),
            "message": f"Kernel for session {session_id} created successfully",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create kernel: {str(e)}"
        )


@router.delete("/kernel")
async def shutdown_kernel(x_session_id: str = Header(..., alias="X-SESSION-ID")):
    """关闭指定 session 的内核"""
    try:
        session_id = x_session_id
        if session_id not in kernel_managers:
            raise HTTPException(
                status_code=404, detail=f"Kernel for session {session_id} not found"
            )

        km = kernel_managers[session_id]
        await km.shutdown_kernel()
        del kernel_managers[session_id]

        return {
            "success": True,
            "message": f"Kernel for session {session_id} shutdown successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to shutdown kernel: {str(e)}"
        )


@router.get("/kernels")
async def list_kernels():
    """列出所有活跃的内核"""
    try:
        kernels = []
        for session_id, km in kernel_managers.items():
            try:
                status = "unknown"
                if km.has_kernel:
                    if await km.is_alive():
                        status = "alive"
                    else:
                        status = "dead"

                kernels.append(
                    KernelInfo(
                        kernel_id=session_id,
                        status=status,
                        connections=1,  # 简化处理
                    )
                )
            except Exception:
                kernels.append(
                    KernelInfo(kernel_id=session_id, status="error", connections=0)
                )

        return {"kernels": kernels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list kernels: {str(e)}")


@router.get("/kernel/status")
async def get_kernel_status(x_session_id: str = Header(..., alias="X-SESSION-ID")):
    """获取指定 session 的内核状态"""
    try:
        session_id = x_session_id
        if session_id not in kernel_managers:
            raise HTTPException(
                status_code=404, detail=f"Kernel for session {session_id} not found"
            )

        km = kernel_managers[session_id]
        status = "unknown"

        if km.has_kernel:
            if await km.is_alive():
                status = "alive"
            else:
                status = "dead"

        return {
            "session_id": session_id,
            "kernel_id": session_id,
            "status": status,
            "workspace": str(get_session_workspace(session_id)),
            "has_kernel": km.has_kernel,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get kernel status: {str(e)}"
        )
