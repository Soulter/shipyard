# Shipyard

一个基于 DinD 技术的 Agent Sandbox 运行环境。

## 架构

User <-> Bay <-> Ship

- Bay 是一个中台，起到管理和调度 Ship 的作用。
- Ship 是一个隔离的容器化执行环境，运行 IPython、Chromium、Shell、File System 等功能。

使用 `Celery` 执行异步任务调度，`Redis` 作为消息中间件。

## Environment

- MAX_SHIP_NUM: 最大允许的 Ship 数量，默认 10
- BEHAVIOR_AFTER_MAX_SHIP: 达到最大 Ship 数量后的行为，默认 "reject"。可选值：
  - "reject": 拒绝新的 Ship 创建请求
  - "wait": 等待直到有 Ship 被释放（默认）
- ACCESS_TOKEN: 访问令牌，用于操作 Ship，默认为 `secret-token`

## Packages

### Bay

包含一个基于 FastAPI 的 API 服务。

#### 接口定义

- `POST /ship` - 创建一个新的 Session，这会启动一个新的 Ship 环境。
- `GET /ship/{ship_id}` - 获取指定 Ship 环境的信息。
- `DELETE /ship/{ship_id}` - 删除指定的 Ship 环境。
- `POST /ship/{ship_id}/exec/{oper_endpoint}` - 在指定的 Ship 环境中执行操作。
- `GET /ship/logs/{ship_id}` - 获取指定 Ship 环境的日志。
- `POST /ship/{ship_id}/extend-ttl` - 延长指定 Ship 环境的生命周期。

上述所有接口都需要请求头：

- `Authorization`: Bearer token

#### Ship Entity

- `id` - 唯一标识符
- `status` - 当前状态。1: running, 0: stopped
- `created_at` - 创建时间
- `updated_at` - 最后更新时间
- `container_id` - 关联的 Docker 容器 ID
- `ip_address` - 容器的 IP 地址
- `ttl` - 生命周期，单位为秒

#### POST /ship

创建一个新的 Ship 环境。

请求体参数：

- `ttl` (int, 必填) - 生命周期，单位为秒。
- `spec` (dict, 可选) - 规格，包含以下可选字段：
  - `cpus` (float, 可选) - 分配的 CPU 数量。
  - `memory` (str, 可选) - 分配的内存大小，例如 "512m"。

返回 Ship 实体。

#### POST /ship/{ship_id}/exec

在指定的 Ship 环境中执行操作。

请求体参数：

- `type` (str, 必填) - 操作的端点，决定执行的具体功能。
- `payload` (dict, 可选) - 传递给具体操作的参数（以 POST 请求体的方式）。

截至目前，`type` 可以是以下值：

- `fs/create_file` - 创建文件
- `fs/read_file` - 读取文件
- `fs/write_file` - 写入文件
- `fs/delete_file` - 删除文件
- `fs/list_dir` - 列出目录内容
- `ipython/exec_code` - 执行 IPython 代码
- `shell/exec` - 执行 Shell 命令

中台会根据 `oper_endpoint` 将请求体转发到对应的 Ship 容器内的 API。

需要请求头：

- `X-Ship-ID` - Ship 的 ID

### Ship

包含一个基于 FastAPI 的 API 服务，运行在 DinD 容器中。
