# AI Capability Hub — 业务 MCP 插件开发与发布契约规范

> **适用对象**：MCP 插件开发者、后端工程师、AI 辅助编程 Agent。  
> **设计理念**：万物皆插件，治理与业务彻底解耦，极简内网交付，全流程自助上线。

---

## 1. 架构总览与平台通用契约 (所有 MCP 均须遵守)

在 AI Capability Hub 体系中，企业内部所有业务能力均以 **独立 MCP 插件微服务** 形式接入，Hub Core 作为统一网关提供安全与治理能力。

### 1.1 通信协议与端点规范
- **传输协议**：统一采用标准 MCP **Streamable HTTP** 协议。
- **协议端点**：微服务必须在根路径挂载 `/mcp` 端点（FastMCP 默认路径为 `/mcp`），用于处理 MCP 握手、工具列表探测（`tools/list`）与工具调用（`tools/call`）。
- **存活探测**：微服务必须提供 HTTP `GET /healthz` 端点，返回状态码 200 及包含 `{"status": "healthy"}` 的 JSON 响应，供容器编排或 Hub 进程守护器执行可用性探测。

### 1.2 工具标识与命名空间隔离规则
为了避免不同业务插件之间的工具函数重名冲突，平台实施明确的命名空间隔离契约：

| 视角 | 工具命名规则 | 示例 (以 `order-service` 为例) | 说明 |
| :--- | :--- | :--- | :--- |
| **插件微服务本地** | 原始函数名 | `query_order` | 开发者在本地编写代码、单测时直接使用原生名称。 |
| **Hub 统一对外暴露** | `{service_id}_{tool_name}` | `order_service_query_order` | FastMCP 动态挂载（`mount`）后暴露给外部 AI 助手的唯一名称。 |
| **Hub 治理与授权标识** | `{service_id}__{tool_name}` | `order-service__query_order` | 数据库持久化主键与权限审批单绑定的标准工具 ID（中间件同时兼容单/双下划线精确匹配）。 |

> [!IMPORTANT]
> 开发者编写插件代码时**绝不需要**手动在工具名中硬编码服务名前缀；Hub 网关在挂载时会自动处理命名空间映射与双向下发。

### 1.3 风险分级与权限管控规范
在声明工具时，开发者必须准确标注操作的风险等级 `risk_level`：
- **`L0`（基础公开级）**：纯只读公开功能（如查询企业公开文档、系统字典、帮助手册）。**全员免审批默认可用**。
- **`L1`（业务读取级）**：涉及特定业务系统数据查询（如按单号查订单、查询个人资产明细）。需由用户在门户申请开通，管理员审批后生效。
- **`L2`（常规写入级）**：涉及业务状态变更或低频写入（如更新订单状态、提交审批、创建草稿）。需管理员审批，且 Hub 默认标记需要人工二次确认。
- **`L3`（高危核心级）**：涉及资金转账、批量生产数据删除、权限提权等敏感操作。强制拦截并执行严格审批与高密级审计。

### 1.4 统一错误处理与返回表达
- **禁止抛出未捕获异常**：当下游业务系统报错、超时或入参不合法时，微服务工具函数应捕获异常并返回结构化字典：
  ```python
  return {
      "success": False,
      "error_code": "RESOURCE_NOT_FOUND",
      "message": "未能查询到对应记录，请检查入参"
  }
  ```
- 返回字典中的结构化数据将由 FastMCP 自动包装为标准 MCP `CallToolResult`。

---

## 2. 官方 Python ZIP 发布包约定与发布器校验规则

针对自研 Python 插件，平台提供脚手架模板并支持通过管理端直接上传 ZIP 压缩包一键上线。

### 2.1 压缩包目录结构约定
```
order-service.zip
├── manifest.json              # [必须] 插件契约元数据清单
├── server.py                  # [必须] 核心入口文件 (FastMCP 服务定义)
├── requirements.txt           # [可选] 额外第三方依赖
├── README.md                  # [推荐] 插件业务说明与快速指南
├── agent.md                   # [推荐] 辅助 AI 迭代开发的上下文指令
└── tests/                     # [推荐] 自动化测试用例
    └── test_server.py
```
> [!NOTE]
> ZIP 包允许所有文件平铺在压缩包根层，也允许包裹在单层同名主文件夹下（例如 `order-service/manifest.json`），发布器会自动解包并平铺落地。

### 2.2 字段来源：开发者必填 vs Hub 自动生成

| 字段名 | 来源 | 说明与校验规则 |
| :--- | :--- | :--- |
| `service_id` | **开发者必填** | 唯一服务标识。必须小写字母开头，仅含小写字母、数字、下划线、连字符（2~63字符），正则：`^[a-z][a-z0-9_-]{1,62}$`。 |
| `name` | **开发者必填** | 服务中文显示名称（如“电商订单服务”）。 |
| `description` | **开发者必填** | 服务的详细业务场景说明。 |
| `entrypoint` | **约定固定** | 官方 Python 脚手架固定为 `server.py`。 |
| `protocol` | **约定固定** | 固定为 `streamable-http`。 |
| `tools` | **开发者必填** | 工具声明数组，每项包含 `name`、`description`、`risk_level`。 |
| `port` | **Hub 运行时分配** | 本地托管模式下，由 Hub 自动探测并分配未占用的空闲端口（默认 8085~8135 范围），无需开发者指定。 |
| `endpoint_url` | **Hub 运行时生成** | Hub 拉起微服务后生成的微服务实际通信端点：`http://127.0.0.1:{port}/mcp`。 |
| `status` | **Hub 状态机维护** | 初始为 `active`，服务宕机或探活失败时流转为 `degraded` 或 `inactive`。 |

### 2.3 发布器校验管道 (inspect -> publish)
当开发者在控制台上传 ZIP 压缩包时，Hub 发布器执行以下原子性校验规则：
1. **路径安全防遍历**：压缩包内严禁出现绝对路径（如 `/etc/passwd`）或包含 `..` 上卷路径，否则拒绝解压。
2. **核心契约文件完整性**：必须同时包含 `manifest.json` 与 `server.py`，任一缺失立即返回 400。
3. **元数据合规检查**：解析 `manifest.json`，校验 `service_id` 正则规则与 JSON 格式。
4. **入口语法预编译检查**：对 `server.py` 执行 `compile(code, 'server.py', 'exec')` 语法检测，若有 Python 语法错误直接拦截并提示具体错误行。
5. **动态端口探活与工具发现**：分配端口启动服务进程，在 10 秒内轮询 `/healthz` 存活检测；通过后主动发起 MCP 协议连接 `/mcp` 执行 `tools/list` 提取工具清单并持久化基线快照。

---

## 3. 服务运行与部署模式

Hub 平台支持以下两种运行模式，开发者可按需选择：

### 模式 A：轻量进程托管模式 (开发联调与轻量上线推荐，免 Docker)
- 在管理端上传 ZIP 后，Hub 内部的 `PluginManager` 自动分配端口拉起子进程（`python server.py`），通过 `.pid` 文件监控进程生命周期。
- 适用于开发调试、Windows/macOS/Linux 单机测试或无 Docker 权限的内网环境。

### 模式 B：Docker 容器集群模式 (生产大规模集群推荐)
- 各业务 MCP 统一复用官方轻量共享镜像底座 `mcp-runner:latest`（基于 `python:3.11-slim`，已内置 fastmcp、httpx、pydantic、sqlalchemy 等绝大多数通用库）。
- 将服务目录映射至容器并在内部接入 `hub-internal` 网络，统一通过容器名寻址。

---

## 4. 可选高级章节：需要个人业务凭据时怎么开发？

默认示例面向“公开无凭据”服务。如果您的业务系统（如企业债券资管系统 TICM、私有 ERP/CRM）需要每个用户使用**自己的专属账号与密码**登录并查询持仓与业务数据，请遵循本规范开发：

### 4.1 凭据声明规范 (`manifest.json`)
`manifest.json` **仅用于声明“需要哪些凭据”以及“哪些工具需要凭据”**，严禁也不能由插件自行声明自己“可信”。插件接收个人凭据**默认不受信任**，必须由平台管理员在管理端独立确认可信状态（并绑定当前插件 `version` 与目标 `endpoint_url`）；一旦插件版本或端点地址变更，可信状态自动失效并须重新确认。

在 `manifest.json` 中增加 `credential_schema` 声明块，并在 `tools` 数组中为每个工具精确声明 `requires_credentials`（`true` / `false`）：
```json
{
  "manifest_version": "1.0.0",
  "service_id": "ticm",
  "version": "1.0.0",
  "name": "TICM 债券资管系统",
  "credential_schema": {
    "enabled": true,
    "auth_type": "username_password",
    "instructions": "请填写您在 TICM 系统的专有业务用户名与密码（公开交易日历无需绑定）",
    "fields": [
      {
        "field_name": "username",
        "label": "业务用户名",
        "field_type": "text",
        "required": true,
        "secret": false
      },
      {
        "field_name": "password",
        "label": "业务密码",
        "field_type": "password",
        "required": true,
        "secret": true
      }
    ]
  },
  "tools": [
    {
      "name": "ticm__trading_calendar",
      "description": "查询银行间债券市场交易日历（公开免绑定）",
      "risk_level": "L0",
      "requires_credentials": false
    },
    {
      "name": "ticm__portfolio_summary",
      "description": "查询个人名下债券持仓汇总（需个人账号）",
      "risk_level": "L1",
      "requires_credentials": true
    }
  ]
}
```

### 4.2 免凭据工具与需凭据工具共存
- 同一插件服务内，公共工具（如 `ticm__trading_calendar` L0 级，`requires_credentials: false`）无需用户绑定凭据即可匿名执行，Hub 向下游发起请求时**绝不注入任何个人凭据头**。
- 同一服务内可同时存在“仅需平台审批但免个人账号”的工具（`risk_level: "L1"` + `requires_credentials: false`）与“既需审批又需个人账号”的工具（`risk_level: "L1"` + `requires_credentials: true`）：门户申请弹窗与“我的 MCP”摘要均按工具级 `requires_credentials` 判定，仅申请免凭据工具时不要求输入密码。
- **凭据要求声明来源与优先级**：`manifest.json` 显式声明 > 下游 MCP `tools/list` 的 `meta["requires_credentials"]` > 刷新工具时由数据库 `preserve_policies=True` 保留的已有声明。即使插件仅在 ZIP 的 `manifest.json` 中声明 `requires_credentials: true`（代码 `@mcp.tool()` 未带 `meta`），管理员刷新工具后仍会保留该凭据要求，不会退化为免凭据。
- 敏感业务工具（如 `ticm__portfolio_summary` L1 级，`requires_credentials: true`）在被调用时，Hub 网关将逐项检查：目标插件是否已由管理员确认为当前版本与目标地址的可信接收方、生产环境是否走受保护传输（HTTPS）、以及调用者是否绑定了有效凭据。任一不满足时，网关在中间件层直接拦截并报错，不会向微服务发起任何网络请求。

### 4.3 运行时凭据传递与隔离边界说明
用户在门户首次申请或配置凭据后，Hub 加密存储层使用对称算法加密入库。AI 和用户客户端只传输普通的业务查询入参（如 `trade_date="2026-11-24"`），**绝不传输密码**。

> [!WARNING]
> **关于 HTTP 请求头明文性与传输保护的强制要求**：  
> `X-Hub-User-Credentials` 请求头承载的是 Hub 服务端解密后的 JSON 字符串，**HTTP 请求头本身并未在应用层加密**。因此：
> 1. **生产环境强制受保护传输**：`HUB_ENV=production` 下，Hub 仅允许通过 `https://`（TLS / 受保护内网通道）向已确认可信的插件转发凭据头，严禁通过明文 `http://` 投递个人凭据。
> 2. **严禁日志泄漏**：插件与业务系统在任何日志、审计或返回体中**严禁**打印 `X-Hub-User-Credentials`、明文密码、Cookie 或下游 `session_id` 标识。

当请求到达受信任的微服务时，FastMCP 工具函数通过 `get_http_request()` 提取 Hub 注入的凭据头，再通过独立的 HTTP 请求向业务系统登录换取 Cookie：
```python
import json
from fastmcp.server.dependencies import get_http_request

# 维护 user_id:credential_version -> Session Cookie 映射
SESSION_CACHE: dict[str, str] = {}

@mcp.tool(meta={"risk_level": "L1", "requires_credentials": True})
async def ticm__portfolio_summary() -> dict:
    """查询个人持仓概况"""
    req = get_http_request()
    user_id = req.headers.get("x-hub-user-id")
    cred_ver = req.headers.get("x-hub-credential-version", "0")
    raw_creds = req.headers.get("x-hub-user-credentials")

    if not raw_creds:
        return {"success": False, "error_code": "UNAUTHORIZED", "message": "未接收到用户业务凭据"}

    creds = json.loads(raw_creds)
    session_key = f"{user_id}:{cred_ver}"

    # 1. 检查是否存在有效会话
    session_cookie = SESSION_CACHE.get(session_key)
    if not session_cookie:
        # 2. 实际 POST 业务登录接口换取 session Cookie（禁止在日志打印 session 标识）
        session_cookie = await login_upstream_system(creds["username"], creds["password"])
        SESSION_CACHE[session_key] = session_cookie

    # 3. 携带专属 Session Cookie 请求业务持仓接口，杜绝跨用户串号
    positions = await fetch_positions(session_cookie)
    return {"success": True, "positions": positions}
```

### 4.4 密码失效与会话失效处理
1. **密码失效或登录失败**：若下游业务系统认证失败，插件必须返回结构化错误 `{"success": False, "error_code": "INVALID_CREDENTIALS", "message": "业务系统用户名或密码错误"}`。
2. **改密与解绑即时失效**：当用户在门户修改密码或点击解绑时，Hub 会自动递增该用户的 `credential_version`。下次调用时请求头携带更新后的版本号，微服务因本地 `session_key` 不匹配自动清空旧会话并重新认证，杜绝旧 Session 残留。

### 4.5 开发者凭据安全红线
1. ❌ **严禁把密码声明为工具函数的输入参数**：AI 会在提示词中向终端用户索要明文密码，或将密码记录在对话日志中。
2. ❌ **严禁在 `manifest.json`、源码或配置文件中写入真实凭据**。
3. ❌ **严禁用全局静态变量共享下游 Session**：必须按调用者工号严格隔离。
