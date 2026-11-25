# AI 协作开发指引 (agent.md)

> **给辅助编码 AI (Cursor / Claude / Copilot / Antigravity) 的精准约束**  
> 当开发者要求你在本插件中新增、修改或重构工具时，你必须严格同步以下三个文件，并完成本地测试交付。无需向开发者解释架构，直接按契约编写生产可用代码。

---

## 1. 改动工具时必须同步的文件清单

每一次工具的新增、重构或废弃，你必须**同时保持以下 3 个文件绝对一致**：

1. **`server.py`（实现层）**：
   - 工具函数必须使用 `@mcp.tool()` 并声明为 `async def`。
   - 所有网络请求使用 `httpx.AsyncClient`，禁止同步阻塞。
   - 必须提供精确详尽的中文 Docstring 与强类型注解（供 LLM 决策入参）。
   - 业务异常必须捕获，返回结构化字典 `{"success": False, "error_code": "...", "message": "..."}`，严禁未捕获抛出 500。
   - 绝不可删除 `@mcp.custom_route("/healthz")` 存活探测端点。
2. **`manifest.json`（平台契约层）**：
   - `tools` 列表中必须严格同步对应工具项：`name`（必须与函数名完全一致）、`description`、`risk_level`（只读设为 `L0`/`L1`；写操作设为 `L2`/`L3`）。
   - `service_id` 必须小写（`^[a-z][a-z0-9_-]{1,62}$`）。
3. **`tests/test_server.py`（自动化验证层）**：
   - 必须覆盖至少 1 个正常参数用例、1 个非法/缺失参数用例，以及 1 个基于 `Client(mcp)` 的内存协议发现与调用断言。

---

## 2. 核心架构契约与约束

- **传输协议**：`streamable-http`，本地开发默认监听 `0.0.0.0:8000`，微服务实际 MCP 交互端点为 `/mcp`。
- **工具命名空间**：
  - 本地微服务内工具名为原始函数名（如 `query_order`）。
  - 发布到 Hub 网关后，Hub 统一暴露的工具名为 `{service_id}_{tool_name}`（如 `order-service_query_order`）。无需在微服务代码内部手动拼接服务名前缀。
- **个人业务凭据规则（如对接私有系统）**：
  - `manifest.json` 只能声明需要凭据（`credential_schema` 与工具级 `requires_credentials`），接收方可信状态必须由平台管理员独立确认并绑定版本与目标地址。
  - 严禁将密码作为工具函数的参数声明（避免 AI 对话向用户索要明文密码）。
  - 运行时凭据通过 `fastmcp.server.dependencies.get_http_request()` 从请求头 `X-Hub-User-Credentials` 读取（注意该请求头本身未做应用层加密，生产环境强制 HTTPS/TLS 受保护传输，且严禁在日志输出凭据或 session 标识）。
  - 必须按 `user_id:credential_version` 隔离 Session，严禁用全局单例共享用户会话。

---

## 3. 交付前必须运行的测试命令

在向开发者汇报完成之前，必须确保在终端执行以下命令并且测试 **100% 通过**：
```bash
pytest -v tests/
```
若有测试失败，必须原地排查并修复，禁止交付未经自测的代码。
