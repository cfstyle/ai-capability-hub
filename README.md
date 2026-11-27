# AI Capability Hub

> 企业级 AI 业务能力中心 — MCP 聚合网关

[![Version](https://img.shields.io/badge/version-0.2.2-blue.svg)]()
[![Status](https://img.shields.io/badge/status-P0%20阶段-orange.svg)]()

## 简介

AI Capability Hub 是面向企业的 AI 业务能力聚合平台。它基于 [Model Context Protocol (MCP)](https://modelcontextprotocol.io) 标准，将分散在各业务系统中的能力统一暴露为标准化的 MCP Tools，供 AI Agent / Copilot 直接调用。

**核心价值：** 让 AI 不再需要逐个对接业务系统，只需连接一个 Hub 即可获得所有已注册的业务能力。

## 架构概览

```
┌───────────────────────┐
│   AI Agent / Copilot  │
│   (MCP Client)        │
└──────────┬────────────┘
           │ MCP (Streamable HTTP)
           ▼
┌───────────────────────┐
│   Hub Core (网关)      │
│   ┌─────────────────┐ │
│   │ MCP 聚合代理     │ │  ← 对外：统一 MCP Server
│   │ (FastMCP Proxy)  │ │  ← 对内：多下游 MCP Client
│   ├─────────────────┤ │
│   │ 服务注册表       │ │  ← 管理下游服务注册
│   ├─────────────────┤ │
│   │ 治理层           │ │  ← 风险分级、审批、审计
│   ├─────────────────┤ │
│   │ REST 管理 API    │ │  ← 运维管理接口
│   └─────────────────┘ │
└──────────┬────────────┘
           │ MCP (Streamable HTTP)
     ┌─────┴──────┐
     ▼            ▼
┌─────────┐  ┌──────────┐
│ TICM    │  │ Message  │
│ MCP     │  │ MCP      │
│ Server  │  │ Server   │
└─────────┘  └──────────┘
 债券资管       内部消息
```

## 快速开始

### 方式一：本地命令行直接开发调试（推荐）

激活你本地配置好的 `py311` conda 环境：

```bash
conda activate py311
```

**1. 启动 TICM Mock MCP Server（端口 8081）：**
```bash
python services/ticm-mcp/server.py
```
> 健康检查：访问 `http://127.0.0.1:8081/healthz` 验证是否正常。

**2. 启动 Message Mock MCP Server（端口 8082，需 Node.js 18+）：**
```bash
cd services/message-mcp
npm install
npm start
```
> 健康检查：访问 `http://127.0.0.1:8082/healthz` 验证是否正常。

**3. 启动 Hub Core 聚合网关（端口 8080）：**
```bash
cd hub-core
uvicorn src.main:app --host 127.0.0.1 --port 8080 --reload
```
> 健康检查：访问 `http://127.0.0.1:8080/healthz`

**4. 运行单元测试：**
```bash
pytest hub-core/tests
```

---

### 方式二：Docker Compose 容器部署（生产发布/隔离验证）

所有 Python 服务（`hub-core` 及 `services/` 下业务 MCP）统一共享 `mcp-runner:latest` 底座镜像，构建时请使用 `scripts/build.sh`：

```bash
# 1. 复制环境变量配置
cp .env.example .env

# 2. 构建共享 Python 底座及各服务镜像
./scripts/build.sh

# （国内网络可使用镜像源参数加速构建）
# APT_MIRROR=http://mirrors.tencent.com \
# PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple \
# NPM_REGISTRY=https://registry.npmmirror.com \
# ./scripts/build.sh

# 3. 启动所有服务
docker-compose up -d

# 4. 检查服务状态与健康检查
docker-compose ps
curl http://localhost:8080/healthz
```

如需打包拷贝至隔离内网环境部署（前端已合并至 `RgOne/frontend`，不再需要导出 `hub-admin` 镜像）：
```bash
docker save \
  mcp-runner:latest \
  ai-capability-hub-hub-core:latest \
  ai-capability-hub-message-mcp:latest \
  | gzip > ai-capability-hub-images.tar.gz
```

## 项目结构

```
ai-capability-hub/
├── hub-core/                  # Hub Core 聚合网关
│   ├── src/
│   │   ├── api/               # REST 管理 API
│   │   ├── gateway/           # MCP 聚合代理
│   │   ├── governance/        # 治理层（风险分级、审批）
│   │   ├── registry/          # 服务注册表
│   │   ├── config.py          # 配置加载
│   │   └── main.py            # 应用入口
│   ├── tests/                 # 测试
│   ├── Dockerfile
│   └── requirements.txt
├── services/
│   ├── ticm-mcp/              # Mock: 债券资管 MCP Server (Python)
│   │   ├── server.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── message-mcp/           # Mock: 内部消息 MCP Server (Node.js)
│       ├── server.js
│       ├── Dockerfile
│       └── package.json
├── docs/                      # 项目文档
├── docker-compose.yml         # 生产编排
├── docker-compose.dev.yml     # 开发覆盖
├── .env.example               # 环境变量模板
└── README.md
```

## 开发指南

### 本地开发环境

**Hub Core（Python）：**

```bash
cd hub-core
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

**TICM Mock Server（Python）：**

```bash
cd services/ticm-mcp
pip install -r requirements.txt
python server.py
```

**Message Mock Server（Node.js）：**

```bash
cd services/message-mcp
npm install
npm start
```

### 运行测试

```bash
cd hub-core
pytest tests/ -v
```

## Mock MCP Server 说明

P0 阶段提供两个独立的 Mock MCP Server，用于验证 Hub 聚合能力：

| 服务 | 端口 | 语言 | 提供的 Tools |
|------|------|------|-------------|
| TICM MCP | 8081 | Python | `ticm__portfolio_summary`, `ticm__bond_detail` |
| Message MCP | 8082 | Node.js | `message__send_notification`, `message__list_pending` |

> **注意：** Mock Server 返回的数据均为模拟数据，`data_status` 字段标记为 `"MOCK"`。

## 当前状态

**版本：** V0.2.2 — P0 阶段（技术验证）

P0 聚焦验证以下关键技术点：

- [x] Hub Core 项目骨架搭建
- [x] Mock MCP Server 实现（TICM + Message）
- [x] FastMCP `create_proxy` + `mount` 聚合机制验证
- [x] 服务动态注册 / 发现
- [x] 基础治理（风险分级、调用日志）

## 相关文档

- [项目架构记忆与发布规范 (Project Memory)](PROJECT_MEMORY.md)
- [ADR-010：自研业务 MCP 服务交付架构与共享底座](docs/adr/ADR-010-业务MCP交付架构与共享底座.md)
- [总体方案](docs/企业级%20AI%20业务能力中心-总体方案.md)
- [V0.2 评审意见与修订决策](docs/AI%20Capability%20Hub%20V0.2%20评审意见与%20V0.2.1%20修订决策.md)
- [V0.2.2 二轮评审回复](docs/AI%20Capability%20Hub%20V0.2.2：二轮评审回复与实施决策.md)

## License

Private — Internal Use Only
