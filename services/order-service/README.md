# Python MCP 标准插件开发脚手架 (python-mcp-demo)

> 本脚手架是 **AI Capability Hub** 官方提供的 Python 3.11+ 标准微服务模板。  
> 默认示例无需数据库、无需企业账号，解压即跑，自带本地单元测试与 FastMCP Client 协议级验证。

---

## ⚡ 开发者第一屏：4 个核心问答

### Q1: 第一次运行，要执行哪几条命令？
```bash
# 1. 确保在脚手架根目录（包含 server.py 与 manifest.json 的目录）
cd services/python-mcp-demo

# 2. 激活 Python 3.11+ 环境并安装依赖 (如需)
# conda activate py311
pip install -r requirements.txt

# 3. 运行随包测试（包含业务函数测试与 FastMCP 协议层工具发现/调用测试）
pytest -v tests/

# 4. 本地启动微服务
python server.py
```
**预期输出**：
- 控制台打印 `Starting MCP server 'Python MCP Demo' with transport 'streamable-http' on http://127.0.0.1:8000/mcp`。
- 探测存活：浏览器或 curl 访问 `http://127.0.0.1:8000/healthz`，返回 `{"status":"healthy","service":"Python MCP Demo","tools_count":2}`。

---

### Q2: 改成自己的 MCP，要替换哪些文件、哪些字段？
仅需关注 **3 个核心文件**，严禁修改不可见的系统私有文件：
1. **`manifest.json`**：
   - `service_id`：改成你的小写唯一标识（如 `order-service`，仅限小写字母、数字、下划线、连字符，2~63字符）。
   - `name` / `description`：改成中文业务服务名与职能说明。
   - `tools` 列表：声明每个工具的 `name`（与代码函数名一致）、`description`、`risk_level`（只读设为 `L0`/`L1`，写操作设为 `L2`/`L3`）。
2. **`server.py`**：
   - `mcp = FastMCP("你的服务名")`：更新服务标识。
   - 删除 demo 工具函数，编写你的 `@mcp.tool()` 异步函数（`async def`），完善 Docstring 与强类型注解。
   - **务必保留**底部的 `@mcp.custom_route("/healthz")` 存活检测路由。
3. **`tests/test_server.py`**：
   - 替换为针对你自己工具函数正常入参、异常/缺失入参的断言。

---

### Q3: 怎样确认新工具在本地已经能被 MCP 客户端发现和调用？
推荐两种零成本验证方式（无需启动 Docker 或部署 Hub）：

- **方式 A（代码内极速自测，最推荐）**：  
  在 `tests/test_server.py` 中直接利用 FastMCP 官方内置的内存 Client 进行验证：
  ```python
  from fastmcp import Client
  from server import mcp

  async with Client(mcp) as client:
      tools = await client.list_tools()
      print("本地已发现工具:", [t.name for t in tools])
      result = await client.call_tool("你的工具名", {"参数名": "测试值"})
      print("调用结果:", result.content[0].text)
  ```
- **方式 B（本地独立 HTTP 联调）**：  
  终端运行 `python server.py` 监听 `8000` 端口，在任何 MCP 客户端（如 Cursor、Claude Desktop、Python 脚本）中配置端点为：
  `http://127.0.0.1:8000/mcp`（传输协议为 `Streamable HTTP`）。

---

### Q4: 怎样打包、上传，并经 Hub 再调用一次？
1. **本地打包**（仅打入源码，切勿包含虚拟环境与缓存）：
   ```bash
   # 在解压后的插件根目录执行：
   zip -r order-service.zip manifest.json server.py requirements.txt README.md agent.md tests/
   ```
2. **上传发布**：  
   登录 Hub 管理端（默认端口 3000 或 8080），在“MCP 服务”页面点击**“发布 MCP 插件”**，上传 `order-service.zip`。平台将自动校验语法、分配端口、拉起微服务并在网关动态挂载。
3. **经 Hub 统一入口再次调用**：  
   挂载到 Hub 后，工具将被添加**服务命名空间前缀**以避免命名冲突：
   - 插件本地原始工具名：`query_order`
   - **经 Hub 统一暴露的调用工具名**：`order-service_query_order`
   - AI 客户端通过 Hub 统一端点 `http://127.0.0.1:8080/mcp` 即可直接发现并调用该工具！

---

## 🛠 贯穿教程：把 Demo 改造为“按订单号查询订单状态”

按以下真实顺序修改，5 分钟内完成自研 `order-service` 开发上线：

### 步骤 1：修改 `manifest.json`
将原有的 `python-mcp-demo` 改为 `order-service`，声明 `query_order` 工具：
```json
{
  "manifest_version": "1.0.0",
  "service_id": "order-service",
  "name": "电商订单服务 MCP",
  "version": "1.0.0",
  "description": "提供订单查询、履约状态追踪及明细核对能力",
  "author": "dev-team",
  "entrypoint": "server.py",
  "protocol": "streamable-http",
  "port": 8000,
  "healthz_path": "/healthz",
  "mcp_path": "/mcp",
  "tools": [
    {
      "name": "query_order",
      "description": "根据订单编号查询订单状态、支付金额与商品明细",
      "risk_level": "L1"
    }
  ]
}
```

### 步骤 2：修改 `server.py`
编写核心业务查询逻辑，规范捕获异常并返回结构化数据：
```python
from __future__ import annotations
import logging, os
from typing import Any, Dict, Optional
from fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP("Order Service")

# 模拟订单业务数据库
ORDERS_DB = {
    "ORD-2026-001": {
        "order_id": "ORD-2026-001",
        "buyer": "张三",
        "amount": 1299.00,
        "status": "PAID",
        "items": ["智能降噪耳机"],
        "created_at": "2026-11-24 10:00:00"
    },
    "ORD-2026-002": {
        "order_id": "ORD-2026-002",
        "buyer": "李四",
        "amount": 88.50,
        "status": "SHIPPED",
        "items": ["Type-C 数据线 2米"],
        "created_at": "2026-11-24 11:30:00"
    }
}

@mcp.tool()
async def query_order(order_id: str) -> Dict[str, Any]:
    """根据订单号查询订单当前状态与购买明细。

    Args:
        order_id: 业务订单编号，如 "ORD-2026-001"

    Returns:
        包含订单详情与执行状态的字典
    """
    clean_id = (order_id or "").strip()
    if not clean_id:
        return {"success": False, "error_code": "INVALID_PARAMS", "message": "订单号不能为空"}

    order = ORDERS_DB.get(clean_id)
    if not order:
        return {
            "success": False,
            "error_code": "ORDER_NOT_FOUND",
            "message": f"未查询到订单号为 '{clean_id}' 的订单记录",
            "available_order_examples": list(ORDERS_DB.keys())
        }

    return {"success": True, "data": order}

@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(request):
    """存活与就绪探测"""
    return JSONResponse({"status": "healthy", "service": "Order Service", "tools_count": 1})

if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="streamable-http", host=host, port=port)
```

### 步骤 3：编写 `tests/test_server.py` 并通过测试
```python
import asyncio
from server import mcp, query_order
from fastmcp import Client

def test_query_existing_order():
    res = asyncio.run(query_order(order_id="ORD-2026-001"))
    assert res["success"] is True
    assert res["data"]["buyer"] == "张三"
    assert res["data"]["amount"] == 1299.00

def test_query_non_existing_order():
    res = asyncio.run(query_order(order_id="ORD-999-NOT-FOUND"))
    assert res["success"] is False
    assert res["error_code"] == "ORDER_NOT_FOUND"

def test_mcp_protocol_client_call():
    async def _test():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            assert any(t.name == "query_order" for t in tools)
            call_res = await client.call_tool("query_order", {"order_id": "ORD-2026-002"})
            assert call_res.is_error is False
            assert "李四" in call_res.content[0].text
    asyncio.run(_test())
```
运行测试：
```bash
pytest -v tests/
```
预期看到 **3 passed**。

### 步骤 4：打包 ZIP
在插件源码根目录下执行（**切勿在外层包含多余父目录，且排除无关临时文件**）：
```bash
# Linux / macOS:
zip -r order-service.zip manifest.json server.py requirements.txt README.md agent.md tests/ -x "*__pycache__*" "*.pytest_cache*" "*.git*"

# Windows PowerShell:
Compress-Archive -Path manifest.json, server.py, requirements.txt, README.md, agent.md, tests -DestinationPath order-service.zip -Force
```

### 步骤 5：在 Hub 管理端发布上线
1. 打开浏览器进入 `http://<hub-host>:3000/#/admin/publish`。
2. 上传 `order-service.zip`，系统将自动进行合规预检（`manifest.json` 与 `server.py` 语法解析）。
3. 点击“确认发布”，Hub 将分配独立端口拉起子进程或容器，健康探测通过后自动完成工具挂载。

### 步骤 6：通过 Hub 验证调用
在本地 AI Harness（如 Cursor、Claude Desktop 或外部 MCP 客户端）配置 Hub 地址 `http://127.0.0.1:8080/mcp`（可从门户 `/api/v1/portal/my-config` 复制标准配置）：
```json
{
  "mcpServers": {
    "ai-capability-hub": {
      "url": "http://127.0.0.1:8080/mcp",
      "headers": {
        "Authorization": "Bearer <你的门户访问Token>"
      }
    }
  }
}
```
- 向 AI 发出指令：“帮我查询订单 ORD-2026-001 的状态”。
- 外部 MCP 客户端从 `http://127.0.0.1:8080/mcp` 发现并调用工具：`order-service_query_order(order_id="ORD-2026-001")`。
- 收到回复：“买家张三，状态 PAID，金额 1299.00 元”。

---

## 🔒 进阶：需要个人业务凭据时怎么开发？（免凭据插件可跳过）

如果您的插件是对接企业私有系统（例如 TICM 债券投资系统、ERP 采购系统），需要用户提供专有用户名和密码才能查询：

1. **在 `manifest.json` 中仅声明“需要凭据”与具体工具要求**（插件默认不受信任，接收个人凭据须由管理员独立确认并绑定版本与目标地址）：
   ```json
   "credential_schema": {
     "enabled": true,
     "auth_type": "username_password",
     "instructions": "请填写您在 TICM 系统的专有业务用户名与密码",
     "fields": [
       {"field_name": "username", "label": "业务账号", "field_type": "text", "required": true, "secret": false},
       {"field_name": "password", "label": "业务密码", "field_type": "password", "required": true, "secret": true}
     ]
   },
   "tools": [
     {"name": "ticm__trading_calendar", "description": "交易日历", "risk_level": "L0", "requires_credentials": false},
     {"name": "ticm__portfolio_summary", "description": "个人持仓", "risk_level": "L1", "requires_credentials": true}
   ]
   ```
2. **在 `server.py` 中提取凭据（注意：HTTP 请求头本身未在应用层加密）**：  
   用户在门户申请开通并加密绑定凭据、且管理员确认接收方信任后，Hub 网关在调用需凭据的工具时将解密后的凭据 JSON 写入 HTTP Headers 转发给受信任插件。**`X-Hub-User-Credentials` 请求头本身并未在应用层加密，生产环境强制通过 HTTPS/TLS 受保护传输通道发送，且严禁在日志中输出请求头或 session 标识**：
   ```python
   import json
   from fastmcp.server.dependencies import get_http_request

   @mcp.tool(meta={"risk_level": "L1", "requires_credentials": True})
   async def ticm__portfolio_summary() -> Dict[str, Any]:
       # 从请求上下文中提取 Hub 注入的调用者身份与解密凭据（依赖受保护传输通道）
       req = get_http_request()
       user_id = req.headers.get("x-hub-user-id", "anonymous")
       cred_ver = req.headers.get("x-hub-credential-version", "0")
       raw_creds = req.headers.get("x-hub-user-credentials")
       creds = json.loads(raw_creds) if raw_creds else {}

       # 根据 user_id:cred_ver 缓存或通过 POST 登录业务系统新建 HTTP Session Cookie
       # 详见仓内参考实现: services/ticm-mcp/server.py
   ```
3. **安全原则**：
   - ❌ **严禁**将密码声明为工具函数的入参参数（避免 AI 在 Prompt 提示词中索要明文密码）。
   - ❌ **严禁**将真实密码写死在 `manifest.json`、代码或环境变量中。
   - ❌ **严禁**使用全局共享变量缓存不同用户的会话，或将 session 标识/Cookie/凭据写入日志。

---

## ❓ 常见失败原因与排查清单

| 故障现象 | 根因说明 | 解决办法 |
|---|---|---|
| **`预检失败: 压缩包缺少 manifest.json / server.py`** | ZIP 打包层级过多（如嵌套了多层解压文件夹），或者文件命名拼写有误。 | 确保 `manifest.json` 与 `server.py` 位于 ZIP 顶层或仅带有一层同名主文件夹。 |
| **`预检失败: service_id 不合规`** | `service_id` 包含大写字母（如 `OrderService`）或特殊符号。 | 统一使用小写中划线或下划线命名，如 `order-service`。 |
| **`插件启动超时：10秒内未通过健康检查`** | 1. 删除了 `/healthz` 路由。<br>2. 语法报错导致进程崩溃。<br>3. 端口被宿主机占用。 | 查看生成的 `service.log` 排查启动日志；确认 `server.py` 保留了 `/healthz` 路由。 |
| **FastMCP Client 报 404** | 客户端连接路径写成了 `/sse`。 | FastMCP Streamable HTTP 协议默认路由为 `/mcp`，连接端点应为 `http://127.0.0.1:8000/mcp`。 |
