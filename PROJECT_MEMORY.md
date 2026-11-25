# AI Capability Hub — 架构记忆与发布规范 (Project Memory)

> **核心原则：严禁将业务 MCP 代码与依赖揉入全量巨石镜像打包！**  
> 详见架构决策记录：[ADR-010：自研业务 MCP 服务交付架构与通用运行底座](docs/adr/ADR-010-业务MCP交付架构与共享底座.md)

---

## 1. 架构定位记忆

1. **Hub Core (端口 8080)**：
   - 角色：**聚合网关与反向代理**（基于 FastMCP Proxy + Mount），非代码执行器。
   - 对外：暴露唯一的统一 MCP Server 端点，AI 客户端（Cursor、Claude、Antigravity 等）**终身只配置这一个 URL**。
   - 对内：作为 MCP Client 连接各个下游子服务；内置治理层（安全拦截、权限校验、调用审计）。

2. **业务 MCP Services (`services/`)**：
   - 角色：各自独立的微服务（端口 8081, 8082, ...）。
   - 协议：采用 Streamable HTTP (SSE) 协议与 Hub Core 内部通信。
   - 语言无关：绝大多数为 Python 自研，但架构上天然支持跨语言（如 Node.js、Go 等）。

---

## 2. 发布与交付理念（极简内网交付）

为解决隔离内网环境下“频繁变更代码导致高频重打并拷贝数 GB Docker 镜像”的痛点，项目统一采用：

### 「通用底座 + 源码外挂 + 三层依赖保障」

```
                  ┌───────────────────────────────┐
                  │    AI 客户端 (IDE / Copilot)   │
                  └───────────────┬───────────────┘
                                  │ http://hub-ip:8080
                                  ▼
                     Hub Core (:8080 网关代理)
                                  │
           ┌──────────────────────┴──────────────────────┐
           ▼                                             ▼
  业务 MCP 1 (:8081)                            业务 MCP 2 (:8082)
┌─────────────────────────────────────────────────────────────────┐
│              通用运行底座 (mcp-runner:latest)                   │
├─────────────────────────────────────────────────────────────────┤
│ 1. 业务代码: 外挂自宿主机 ./services/<mcp-name>:/app (改代码免重载)│
│ 2. 共享依赖: 外挂自宿主机 /data/shared-packages -> PYTHONPATH    │
│ 3. 离线 Wheel: 挂载 /data/wheels，启动时按需离线自装            │
└─────────────────────────────────────────────────────────────────┘
```

### 关键实施规范：
1. **只打一个通用底座镜像**：
   - Python MCP 服务统一复用 `mcp-runner:latest`（微胖底座，约 300MB，预装 fastmcp、httpx、pydantic、sqlalchemy、redis 等常用库）。
   - **禁止**为单个新增的 Python MCP 编写独立 Dockerfile 并单独构建镜像。
2. **源码挂载（Volume Mount）**：
   - 业务代码通过卷挂载入容器。更新代码只需覆盖宿主机上的 `.py` 脚本文件，由框架热重载，**秒级生效，0 次 Docker 构建**。
3. **依赖三层演进规范**：
   - **底座预设**：基础镜像预装覆盖 90% 需求。
   - **全局共享依赖池**：引入跨服务通用新库时，在内网机器执行 `pip install --target=/data/shared-packages <wheel>`，注入全局 `PYTHONPATH`，所有容器免重启即刻可用。
   - **单服务独立自装**：服务专属依赖通过宿主机 `/data/wheels` 目录挂载，容器启动脚本检测 `requirements.txt` 自动静默安装。

---

## 3. 镜像构建、VPS 打包与内网交付规范

1. **统一构建顺序（必须先建底座）**：
   - `hub-core/Dockerfile` 以 `mcp-runner:latest` 为基础镜像（`FROM mcp-runner:latest`），`ticm-mcp` 等 Python MCP 服务在 `docker-compose.yml` 中直接复用 `image: mcp-runner:latest` + 卷挂载 `./services/<name>:/app:ro`。
   - **禁止直接跳过底座单独执行 `docker-compose build`**，统一使用 `./scripts/build.sh`（自动先构建 `mcp-runner:latest`，再执行 `docker-compose build`）：
     ```bash
     # 默认构建
     ./scripts/build.sh

     # 国内环境 / 测试打包 VPS（腾讯云）加速构建
     APT_MIRROR=http://mirrors.tencent.com \
     PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
     NPM_REGISTRY=https://registry.npmmirror.com \
     ./scripts/build.sh
     ```

2. **目录挂载约定（`docker-compose.yml`）**：
   - `hub-core` 与各 Python MCP 容器统一挂载 `./data/shared-packages:/shared-packages:ro` 与 `./data/wheels:/wheels:ro`。
   - `hub-core` 挂载 `./services:/app/services`，确保通过管理端 ZIP 上传动态发布的插件在容器重建后不丢失，且子进程直接继承 `mcp-runner` 的完整依赖与 `PYTHONPATH=/shared-packages`。

3. **离线导出与内网部署**：
   - 在测试/打包机导出离线镜像包（`mcp-runner:latest` 与 `hub-core` 的共享底层会在 `tar` 中自动去重）：
     ```bash
     docker save \
       mcp-runner:latest \
       ai-capability-hub-hub-core:latest \
       ai-capability-hub-message-mcp:latest \
       ai-capability-hub-hub-admin:latest \
       | gzip > ai-capability-hub-images.tar.gz
     ```
   - 拷贝到内网服务器后执行 `docker load -i ai-capability-hub-images.tar.gz` 并 `docker-compose up -d`。后续仅更新 Python 业务 MCP 代码时，只需同步宿主机 `./services/` 目录即可，无需重打或重新导出镜像。
