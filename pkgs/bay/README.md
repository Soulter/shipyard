# Bay API Service

Bay API是Agent Sandbox的中台服务，负责管理和调度Ship容器环境。

## 安装和运行

### 使用uv（推荐）

1. 安装uv包管理器：

```bash
pip install uv
```

2. 安装依赖：

```bash
uv pip install -e .
```

3. 复制环境配置：

```bash
cp .env.example .env
# 编辑.env文件，设置数据库连接等配置
```

4. 运行数据库迁移：

```bash
alembic upgrade head
```

5. 启动服务：

```bash
python run.py
```

### 使用Docker Compose

**重要**: Bay现在使用宿主机的Docker socket，而不是Docker-in-Docker模式，这提供了更好的性能和稳定性。

1. 确保宿主机上已经安装了Docker并且Docker daemon正在运行。

2. 构建Ship镜像（在宿主机上）：

```bash
cd ../ship
docker build -t ship:latest .
cd ../bay
```

3. 创建Docker网络（用于Ship容器）：

```bash
docker network create shipyard
```

4. 启动所有服务：

```bash
docker-compose up -d
```

## API端点

### 认证

所有API端点都需要Bearer token认证：

```
Authorization: Bearer <your-access-token>
```

### Ship管理

- `POST /ship` - 创建新的Ship环境
- `GET /ship/{ship_id}` - 获取Ship信息
- `DELETE /ship/{ship_id}` - 删除Ship环境
- `POST /ship/{ship_id}/exec/{oper_endpoint}` - 在Ship中执行操作
- `GET /ship/logs/{ship_id}` - 获取Ship容器日志
- `POST /ship/{ship_id}/extend-ttl` - 延长Ship生命周期

### 健康检查

- `GET /health` - 服务健康检查
- `GET /` - 根端点

## 环境变量

参考 `.env.example` 文件了解所有可配置的环境变量。

主要配置项：

- `ACCESS_TOKEN`: API访问令牌
- `DATABASE_URL`: SQLite数据库文件路径
- `MAX_SHIP_NUM`: 最大Ship数量
- `BEHAVIOR_AFTER_MAX_SHIP`: 达到最大Ship数量后的行为（reject/wait）
- `DOCKER_IMAGE`: Ship容器镜像名称
- `SHIP_HEALTH_CHECK_TIMEOUT`: Ship健康检查最大超时时间（秒，默认60）
- `SHIP_HEALTH_CHECK_INTERVAL`: Ship健康检查间隔时间（秒，默认2）
- `DOCKER_NETWORK`: Docker网络名称

## 开发

### 代码格式化

使用 `ruff`:

```bash
ruff format app/
ruff check app/
```

### 类型检查

使用mypy：

```bash
mypy app/
```

### 测试

```bash
pytest
```

### 数据库迁移

创建新的迁移：

```bash
alembic revision --autogenerate -m "description"
```

应用迁移：

```bash
alembic upgrade head
```
