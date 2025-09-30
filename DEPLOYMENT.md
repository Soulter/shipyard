# Shipyard 部署指南

Shipyard 是一个轻量级 Agent Sandbox 运行环境，支持多 Session 的 Sandbox 复用。本指南将帮助你快速部署 Shipyard。

## 快速开始

### 1. 环境要求

- Docker 和 Docker Compose
- Linux 系统（推荐）

### 2. 使用 Docker Compose 部署

创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  shipyard-bay:
    image: soulter/shipyard-bay:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///./data/bay.db
      - ACCESS_TOKEN=secret-token
      - MAX_SHIP_NUM=10
      - BEHAVIOR_AFTER_MAX_SHIP=wait
      - DOCKER_IMAGE=soulter/shipyard-ship:latest
      - DOCKER_NETWORK=shipyard
    volumes:
      - bay_data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - shipyard
    restart: unless-stopped

volumes:
  bay_data:

networks:
  shipyard:
    driver: bridge
```

### 3. 启动服务

```bash
docker compose up -d
```

### 4. 验证部署

访问 `http://localhost:8000/docs` 查看 API 文档，或者发送测试请求：

```bash
curl -X GET "http://localhost:8000/health" \
  -H "Authorization: Bearer secret-token"
```

## 环境变量配置

| 环境变量 | 描述 | 默认值 |
|---------|------|--------|
| `ACCESS_TOKEN` | API 访问令牌 | `secret-token` |
| `MAX_SHIP_NUM` | 最大允许的 Ship 数量 | `10` |
| `BEHAVIOR_AFTER_MAX_SHIP` | 达到最大 Ship 数量后的行为 | `wait` |
| `DATABASE_URL` | 数据库连接字符串 | `sqlite+aiosqlite:///./data/bay.db` |
| `DOCKER_IMAGE` | Ship 容器镜像 | `soulter/shipyard-ship:latest` |
| `DOCKER_NETWORK` | Docker 网络名称 | `shipyard` |
