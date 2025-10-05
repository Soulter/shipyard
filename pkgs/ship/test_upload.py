#!/usr/bin/env python3
"""
测试Ship的文件上传功能

使用方法:
python test_upload.py
"""

import asyncio
import aiohttp
import tempfile
import os


async def test_upload():
    """测试文件上传功能"""
    base_url = "http://localhost:8123"
    session_id = "test-session-123"

    # 创建测试文件
    test_content = b"Hello, this is a test file!\nLine 2\nLine 3"

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(test_content)
        temp_file_path = temp_file.name

    try:
        async with aiohttp.ClientSession() as session:
            # 测试1: 上传到相对路径
            print("测试1: 上传到相对路径")
            with open(temp_file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field(
                    "file", f, filename="test.txt", content_type="text/plain"
                )
                data.add_field("file_path", "uploaded/test.txt")

                headers = {"X-SESSION-ID": session_id}

                async with session.post(
                    f"{base_url}/upload", data=data, headers=headers
                ) as resp:
                    result = await resp.json()
                    print(f"状态码: {resp.status}")
                    print(f"响应: {result}")
                    print()

            # 测试2: 上传到绝对路径（应该在session工作目录内）
            print("测试2: 上传到session工作目录内的绝对路径")
            with open(temp_file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field(
                    "file", f, filename="test2.txt", content_type="text/plain"
                )
                data.add_field(
                    "file_path", f"/workspace/{session_id}/absolute/test2.txt"
                )

                headers = {"X-SESSION-ID": session_id}

                async with session.post(
                    f"{base_url}/upload", data=data, headers=headers
                ) as resp:
                    result = await resp.json()
                    print(f"状态码: {resp.status}")
                    print(f"响应: {result}")
                    print()

            # 测试3: 尝试上传到session工作目录外（应该失败）
            print("测试3: 尝试上传到session工作目录外（应该失败）")
            with open(temp_file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field(
                    "file", f, filename="test3.txt", content_type="text/plain"
                )
                data.add_field("file_path", "/etc/passwd")  # 危险路径

                headers = {"X-SESSION-ID": session_id}

                async with session.post(
                    f"{base_url}/upload", data=data, headers=headers
                ) as resp:
                    result = await resp.json()
                    print(f"状态码: {resp.status}")
                    print(f"响应: {result}")
                    print()

            # 测试4: 测试路径穿越攻击（应该失败）
            print("测试4: 测试路径穿越攻击（应该失败）")
            with open(temp_file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field(
                    "file", f, filename="test4.txt", content_type="text/plain"
                )
                data.add_field("file_path", "../../../etc/passwd")  # 路径穿越

                headers = {"X-SESSION-ID": session_id}

                async with session.post(
                    f"{base_url}/upload", data=data, headers=headers
                ) as resp:
                    result = await resp.json()
                    print(f"状态码: {resp.status}")
                    print(f"响应: {result}")
                    print()

            # 测试5: 健康检查
            print("测试5: 健康检查")
            async with session.get(f"{base_url}/health") as resp:
                result = await resp.json()
                print(f"状态码: {resp.status}")
                print(f"响应: {result}")
                print()

    finally:
        # 清理临时文件
        os.unlink(temp_file_path)


if __name__ == "__main__":
    print("开始测试Ship文件上传功能...")
    print("确保Ship服务在 http://localhost:8123 运行")
    print("=" * 50)

    asyncio.run(test_upload())
