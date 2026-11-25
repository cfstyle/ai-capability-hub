# 企业级 AI 业务能力中心（AI Capability Hub）
## V0.2.2 架构设计与分阶段实施方案

**项目阶段：** 技术验证与最小可行产品（MVP）  
**目标环境：** 银行隔离内网  
**首个测试客户端：** DeepSeek Harness  
**核心接入协议：** MCP Streamable HTTP（以 `2026-07-28` 为基线，详见 [ADR-006](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-006-协议版本兼容.md)）  
**核心技术栈：** Python 3.11+ / FastMCP / FastAPI / SQLite（详见 [ADR-001](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-001-技术栈与部署.md)）  
**交付方式：** Docker Compose 离线镜像交付（详见 [ADR-001](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-001-技术栈与部署.md)）  
**文档用途：** 供独立开发团队或 AI Coding Agent 执行

---

## 一、项目背景与建设目标

### 1.1 背景

银行内部已存在大量业务系统，包括资金业务管理、协同办公、邮件、运营管理、人力资源及各类自建系统。

这些系统通常具有大量内部 API，但缺少面向 AI Agent 的标准化业务能力接口。

与此同时，企业内网已逐渐具备本地大模型、Agent Harness、Skills 和 MCP 工具调用等基础设施。

当前主要矛盾不在于缺少 Agent，而在于现有 Agent 无法便捷、安全地操作银行内部业务系统。

### 1.2 核心目标

建设一个独立于具体 Agent Harness 的企业 AI 业务能力中心，实现：

1. 将银行内部业务系统的功能抽象为标准化、可复用的业务能力。
2. 支持 Python、Java、Go、Node.js 等不同技术栈开发 MCP Server。
3. 支持已有第三方 MCP Server 无须修改业务代码即可注册接入。
4. 对多个 MCP Server 实现统一发现、授权、路由、审计和管理。
5. 通过 Streamable HTTP 向不同 Agent Harness 提供标准能力。
6. 逐步形成允许不同开发人员独立贡献的插件化能力生态。

### 1.3 非目标

本项目不建设新的 Agent Harness、大模型平台、通用工作流引擎或数字员工客户端。

不要求开发人员使用统一编程语言、统一框架或固定的内部项目目录。

不要求将业务系统全部 API 转换为 MCP Tools。

---

## 二、总体架构

采用**控制面与执行面分离、核心平台与业务能力分离**的架构。

### 2.1 Agent 客户端层

支持 DeepSeek Harness、联合银行数字员工及其他兼容的 MCP 客户端。

客户端只需通过标准协议访问 Hub，不应依赖 Hub 的内部开发语言和框架。

### 2.2 Hub Core：平台核心与技术选型

Hub Core 开发语言采用 **Python 3.11+**，技术组合如下（详见 [ADR-001](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-001-技术栈与部署.md)）：
- **MCP 聚合与代理：** 优先采用 FastMCP（`create_proxy + mount`）进行聚合代理验证，底层依赖官方 `mcp` SDK 2.x（详见 [ADR-007](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-007-聚合实现路径.md)）。
- **管理 REST API：** FastAPI。
- **服务网关与容器：** ASGI + Uvicorn。
- **下游网络访问：** HTTPX，优先使用 SDK 提供的 MCP Client 传输层。
- **数据校验与配置：** Pydantic、PyYAML。
- **数据持久化：** SQLite（MVP 单实例），后续根据并发演进至 PostgreSQL。

Hub Core 包含四个逻辑模块与明确的端点规划：

**Registry：能力注册中心**

- 注册、更新和下线 MCP Server。
- 维护服务标识、地址、版本、负责人及所属业务系统。
- 自动发现并保存工具定义，生成契约快照（详见 [ADR-005](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-005-工具发现与缓存.md)）。
- 检测工具名称冲突、契约变更及服务可用性。
- 支持按系统、业务类别、风险等级查询工具。

**Gateway：聚合 MCP Server 调用网关**

- 采用**聚合 MCP Server 模式**（详见 [ADR-002](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-002-聚合网关模式.md)）：对外表现为一个标准的 MCP Server（客户端仅需配置 Hub 一个地址），对内作为多个下游业务服务的 MCP Client。
- **能力边界：** MVP 阶段**只聚合 MCP Tools**，不聚合 Resources 和 Prompts，暂不支持复杂的反向调用与交互式协议扩展（详见 [ADR-002](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-002-聚合网关模式.md)）。
- 提供统一工具命名空间（`{service_id}__{tool_name}`），避免不同服务之间的名称冲突（详见 [ADR-005](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-005-工具发现与缓存.md)）。
- **对外无状态设计：** 基于 MCP `2026-07-28` 规范，Hub 对外提供无状态 Streamable HTTP 端点，业务执行和用户授权独立于 MCP 连接状态；对依赖旧版协议（如 `2025-11-25`）的下游服务，由内部适配层管理其连接与会话（详见 [ADR-003](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-003-Session管理.md)）。
- **聚合实现路径：** P0 阶段优先验证 FastMCP `create_proxy + mount` 机制及父级 Middleware 拦截能力，设立四项验证标准（工具发现过滤、调用独立授权审计、动态接入、禁止 Token 透传），若不满足则退回官方 `mcp` SDK 自研代理（详见 [ADR-007](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-007-聚合实现路径.md)）。
- **服务发现响应（server/discover）：** 仅发布 Hub 自身能力声明与元数据，`ttlMs=0`，`cacheScope=private`，不汇总或透传下游服务信息（详见 [ADR-008](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-008-服务发现响应.md)）。
- 支持超时、限流和调用链路追踪。

**Governance：统一治理模块**

- 识别并验证调用主体身份（从 HTTP Authorization Header 中解析，严禁依赖模型自然语言入参）。
- 校验工具级访问权限和数据范围，向客户端动态返回当前用户授权的工具目录（详见 [ADR-005](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-005-工具发现与缓存.md)）。
- 管理工具风险等级（L0～L3）。
- 阻止未经授权的敏感操作，禁止客户端 Token 向下游直接透传（详见 [ADR-004](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-004-身份授权.md)）。
- 记录结构化工具调用与业务操作审计日志。
- 预留人工确认、审批及权限撤销接口。

**端点规划与管理接口**

MVP 阶段采用**同进程、不同路由、认证严格分离**的设计（详见 [ADR-009](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-009-端点与管理接口.md)）：
- `/mcp`：供 Harness 等 Agent 客户端访问的标准 MCP 端点，校验客户端/用户 JWT。
- `/api/v1/*`：供管理员执行服务注册、更新、下线及契约刷新的 REST API，采用独立 Admin 认证。
- `/healthz`、`/readyz`：容器存活与就绪健康检查端点。

### 2.3 业务能力服务层

采用独立部署模式。每个业务团队可以维护自己的 MCP Server。例如：

- TICM MCP：债券持仓查询、交易记录核对、经营收益分析。
- OA MCP：待办查询、流程详情、草稿创建。
- 邮件 MCP：邮件查询、附件处理、授权发送。
- 运营管理 MCP：统计指标查询、业务数据汇总。

各服务可以采用不同技术栈，不需要与 Hub Core 共用代码仓库。

### 2.4 系统适配层

各业务服务内部根据需要实现 SystemAdapter，负责：

- 原业务系统身份认证及会话管理。
- 调用底层 REST API 或其他获授权的接口。
- 组合多个接口并转换数据格式。
- 执行业务规则和数据校验。
- 处理上游异常及结果核验。

Hub Core 不直接承担各业务系统的专有逻辑。

### 2.5 部署架构与交付方式

采用 **Docker Compose 离线镜像交付**（详见 [ADR-001](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-001-技术栈与部署.md)）：
1. 在可联网构建环境中构建完整镜像，固定所有依赖版本并生成 SBOM 及镜像摘要。
2. 导出离线镜像包，经银行安全合规检测后导入隔离内网。
3. 通过 Docker Compose 统一编排启动 Hub Core 与 Mock MCP Server。
4. SQLite 数据库文件、注册配置及审计日志挂载至宿主机持久化 Volume。
5. 容器处于同一内部 Docker 网络，仅 Hub Core 对外部 Agent 客户端暴露端口，下游 MCP Server 默认不直接暴露。
6. 禁止在生产内网现场动态拉取镜像或执行 `pip install`。

---

## 三、MCP 插件化接入规范

### 3.1 接入方式

V0.2 优先支持**已部署的远程 MCP Server 注册接入**。

开发者提供：

- MCP Server 访问地址。
- 唯一服务标识与版本。
- 服务名称、业务用途和所属系统。
- 维护负责人。
- 身份认证方式及接入所需的安全配置。
- 工具清单及业务权限说明。

Hub 自动连接服务、执行协议协商、发现工具并建立工具目录。

### 3.2 必须支持跨语言接入

以下服务均应能够独立注册：

- Python 开发的 TICM MCP。
- Java 开发的 OA MCP。
- Node.js 开发的邮件 MCP。
- 符合协议的第三方远程 MCP Server。

不得强制要求业务开发人员引入 Hub 专属 SDK，或修改现有项目的内部目录结构。

### 3.3 服务注册与工具注册

服务与工具分开管理。每个 MCP Server 拥有唯一的服务 ID。

每项 MCP Tool 拥有稳定的工具标识。采用命名空间规范（详见 [ADR-005](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-005-工具发现与缓存.md)）：
- 服务 ID：`ticm`
- 业务能力 ID：`finance.ticm.portfolio.summary`
- 对外工具名称：`ticm__portfolio_summary`（映射规则：`{service_id}__{tool_name}`）

注册时若发现工具名称冲突直接拒绝。

### 3.4 工具发现与生命周期策略

确立三重发现与契约管理机制（详见 [ADR-005](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-005-工具发现与缓存.md)）：
1. **注册时发现：** 连接下游读取工具清单与 Schema，记录基线快照。
2. **启动时校验：** Hub 启动时自动检查已激活服务的一致性。
3. **管理员主动刷新：** 契约发生不兼容变更时需管理员显式触发并审核确认，未经审核不替换已发布契约。
4. **服务健康与目录关系：** 服务偶发中断时不立即从目录删除工具，标记为不可用并在调用时报错，避免扰乱 Agent 上下文；仅在正式停用或安全隔离时才注销。

### 3.5 接入元数据

优先兼容 MCP Registry 的公开元数据规范，包含业务系统归属、数据敏感等级、业务风险等级、所需授权范围、人工确认要求、协议版本等扩展元数据。

### 3.6 第三方现成 MCP

第一版仅支持注册和代理经过审核的远程 MCP Server。stdio 受控桥接、OCI 镜像发布、OpenAPI 自动适配等高级功能留待后续版本研究。

---

## 四、业务能力开发规范

### 4.1 MCP Server 接入规范（强制）

所有接入 Hub 的 MCP Server 必须满足：

1. **协议基线：** 优先采用 MCP `2026-07-28` 规范；条件兼容 `2025-11-25`；首版不支持早期 `2024-11-05` HTTP+SSE（详见 [ADR-006](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-006-协议版本兼容.md)）。
2. **仅支持可代理的 MCP 工具：** 下游服务若依赖客户端主动回调、长任务流式采样或私有会话，Hub 标记为暂不支持，禁止静默降级（详见 [ADR-003](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-003-Session管理.md)）。
3. 提供合法、稳定的 Tool 名称及参数 Schema。
4. 提供明确的输入输出语义。
5. 能够正确返回成功、失败和标准化的业务异常。
6. 提供必要的身份认证与安全能力。
7. 声明工具用途及风险属性。
8. 能够识别服务版本及维护责任人。
9. 通过协议兼容、安全及基础集成测试。

不限制其内部语言、框架、目录和业务实现方式。

### 4.2 标准业务能力开发规范（推荐，高风险业务强制）

对于银行自建核心业务能力，进一步要求：

- 一个工具对应边界清晰、可独立验证的业务操作。
- 可以组合多个底层 API。
- 不将原系统的所有接口机械映射为 Tools。
- 关键金融计算使用确定性程序实现。
- 明确业务口径、数据时点和数据完整性。
- 明确用户权限与机构、账户等数据范围。
- 写入操作提供幂等或重复提交防护。
- 对超时、失败及部分成功建立明确处理规则。
- 提供可重复执行的业务测试用例。
- 不允许模型仅凭自然语言改变权限或业务约束。

### 4.3 开发者 SDK 原则

SDK 是辅助工具，不是强制依赖。初期不开发多语言 SDK。符合协议规范的服务即使不使用 Hub SDK 也能够接入。

---

## 五、身份、权限与安全设计

### 5.1 身份主体与判定原则

系统严格区分：
- 登录用户。
- Agent 或客户端。
- 工具服务。
- 实际业务操作主体。

**核心红线：** 严禁通过大模型生成的员工号、机构号等参数判定访问权限，必须从受信任的传输层 HTTP Authorization Header 中解析身份声明（详见 [ADR-004](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-004-身份授权.md)）。

### 5.2 权限控制

建立分级自治模型：
- L0：授权范围内的普通查询。
- L1：分析、计算、生成内部草稿。
- L2：受控写入及内部流程提交。
- L3：高风险操作及正式审批决策。

风险级别由确定性权限引擎执行，不允许仅依靠 Prompt 约束。

### 5.3 用户授权与两阶段演进策略

身份鉴权实施分阶段演进（详见 [ADR-004](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-004-身份授权.md)）：
- **P0～P2 阶段（模拟业务与框架验证）：** 使用本地签名测试 JWT（包含至少两个不同权限范围的测试主体，如普通员工与投资经理）。下游 MCP Server 使用独立的测试凭据。
- **P3 阶段（真实业务接入）：** 接入真实 TICM 前，必须完成正式身份委托机制建设（建立用户真实身份到业务系统的可信权限映射）；若无法建立可信委托，禁止接入真实生产数据。

### 5.4 禁止 Token 透传（Anti-Token-Passthrough）

禁止将客户端传入 Hub 的 Authorization Bearer Token 直接无条件透传给下游业务系统。Hub 与下游 MCP Server 之间采用独立受控的服务间身份凭据，或基于受校验用户上下文换取的受限凭证（详见 [ADR-004](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-004-身份授权.md)）。

### 5.5 工具缓存与授权隔离

- 客户端调用 `tools/list` 时，Hub 根据当前用户身份令牌中的权限声明过滤工具列表，仅返回该用户被授权的工具。
- 严禁全局缓存全量工具目录供所有用户共享。
- 协议层对外设置 `ttlMs = 0`，`cacheScope = private`，防止客户端或反向代理缓存过期或越权目录（详见 [ADR-005](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-005-工具发现与缓存.md), [ADR-008](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-008-服务发现响应.md)）。

### 5.6 调用审计与安全边界

- 结构化日志记录：调用时间、关联 ID、用户与客户端身份、MCP Server 与 Tool、版本、鉴权结果、耗时、结果状态。敏感凭据与数据严格脱敏。
- 生产环境启用 TLS 加密，管理接口与工具调用接口认证分离（详见 [ADR-009](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-009-端点与管理接口.md)）。
- 未获授权或权限状态不明确时默认拒绝执行，预留紧急熔断与停用开关。

---

## 六、第一阶段 MVP 范围

### 6.1 核心验证目标

同时实现：
1. 一个最小可用的 Hub Core（聚合网关、治理与注册）。
2. 两个完全独立的 MCP Server（不同技术栈）。
3. 一个能够通过 Hub 调用工具的 Agent 客户端（DeepSeek Harness）。

### 6.2 Hub Core 最小功能

- 远程 MCP Server 注册与状态维护（SQLite 持久化）。
- 工具发现、基线快照与按权限过滤。
- 统一命名空间管理（`{service_id}__{tool_name}`）。
- Streamable HTTP 代理调用与错误处理。
- 测试 JWT 身份认证与工具权限校验。
- 结构化调用审计日志。
- 服务启用、停用与健康检查（`/healthz`, `/readyz`）。
- Docker Compose 离线打包与部署。

### 6.3 MCP Server A：TICM

- 技术栈：Python 3.11+。
- 初始 Tool：`ticm__portfolio_summary`。
- 业务功能：获取债券持仓概况（第一步模拟数据，P3 接入授权 TICM 真实数据）。
- 架构要求：业务逻辑、底层 API 适配与 MCP 协议层完全解耦。

### 6.4 MCP Server B：独立测试服务

- 技术栈：Node.js 或 Java。
- 提供模拟内部消息工具：`message__send_notification`。
- 独立部署于独立容器，不引用 Hub 内部模块。
- 验证 Hub 在不修改核心代码情况下的跨语言接入能力。

### 6.5 Agent 验证场景

- 测试客户端：DeepSeek Harness。
- 验证任务：“查询当前债券持仓概况，按品种生成简要分析，并通过内部消息工具生成一条通知记录。”
- 验证链路：Harness 发现授权工具 → 调用 TICM 持仓工具 → 生成分析 → 调用模拟消息工具 → Hub 完整记录两次审计并返回结果。

---

## 七、分阶段执行计划

```
+-----------------------------------------------------------------------------------+
| P0：协议兼容与技术验证                                                             |
| 目标：1 个 Harness + 1 个 Hub + 1 个 Mock MCP                                      |
| 验证：MCP 握手/发现、tools/list、tools/call、FastMCP 代理挂载与拦截能力、Docker 部署 |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| P1：Hub 最小内核实现                                                              |
| 目标：Registry 存储、Gateway 代理、JWT 测试认证、工具权限过滤、结构化审计日志       |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| P2：多服务聚合与插件化验证                                                         |
| 目标：独立接入第 2 个异构 MCP Server，验证工具聚合、命名冲突、异常处理与动态注册   |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| P3：真实业务对接与正式授权                                                         |
| 目标：完成正式身份委托映射，对接真实 TICM 业务数据，完成口径一致性校验与安全验收    |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| P4：多客户端与开发者生态                                                           |
| 目标：接入第 2 个 Harness，邀请独立开发者接入新服务，形成能力接入与开发规范 V1.0     |
+-----------------------------------------------------------------------------------+
```

### P0：技术兼容性验证（核心收敛）

**核心目标：**
证明选定的聚合代理技术路线，在目标 Harness 上可以完成标准 MCP 工具调用。

**最小验证组合：**
- DeepSeek Harness + Hub Core + Mock MCP Server。
- 验证 FastMCP `create_proxy + mount` 机制及父级 Middleware 拦截能力（四项准入标准，详见 [ADR-007](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-007-聚合实现路径.md)）。
- 验证目标 Harness 对 MCP `2026-07-28` 协议及自定义 Authorization Header 的支持能力（详见 [ADR-006](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-006-协议版本兼容.md)）。
- 验证 Docker Compose 离线镜像构建与交付流程（详见 [ADR-001](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-001-技术栈与部署.md)）。

**通过条件：** Harness 能够通过 Hub 成功发现并调用 Mock MCP 工具，确定 FastMCP 是否正式采用或退回官方 SDK。

### P1：实现 Hub 最小内核

- 实现 SQLite Registry 存储层。
- 实现 Gateway 基础代理与命名空间映射。
- 实现签名测试 JWT 认证与用户工具权限过滤。
- 实现结构化调用日志与异常拦截。
- 实现端点分离（`/mcp`、`/api/v1/*`、`/healthz`、`/readyz`）。

### P2：验证插件化能力

- 独立部署 TICM 模拟 MCP 与第二个不同技术栈的 Mock MCP。
- 验证双服务工具聚合、命名重名冲突检测、异常透传与隔离。
- 验证服务受控刷新与动态注册机制。

### P3：接入真实业务能力

- 建设正式身份委托机制，完成与 TICM 权限系统的可信映射。
- 对接 TICM 真实查询接口，校验持仓口径与数据一致性。
- 严格验证无权限、无数据、网络超时及数据范围隔离。

### P4：多客户端与协作验证

- 接入第二种兼容 MCP 的 Agent Harness。
- 邀请独立开发人员根据接入规范接入新业务能力，验证 Hub 扩展性与文档完整性。
- 发布能力中心设计规范 V1.0。

---

## 八、必须覆盖的测试场景

1. MCP Server 无法连接、崩溃或运行中断。
2. Tool 不存在、被停用或当前用户未获授权。
3. 两个不同服务注册了同名 Tool（命名冲突检测）。
4. Tool 输入参数缺失或类型与 Schema 不符。
5. 下游业务系统超时、返回 5xx 异常或数据部分缺失。
6. 服务升级后 Tool Schema 发生不兼容变更（契约审核拦截）。
7. 用户尝试查询超出其授权范围的机构或账户数据。
8. 客户端在未携带有效 Authorization Token 时调用受保护工具。
9. 多用户并发调用时身份上下文与数据隔离无串用。
10. 大模型 Prompt 提示词注入尝试覆盖系统授权身份（防御验证）。
11. 目标 Harness 在新旧协议版本下的协商与兼容性。
12. 工具调用失败后审计流水完整可追溯。

---

## 九、MVP 最终验收标准

必须全部满足：

- [ ] DeepSeek Harness 可通过 Hub 发现并调用工具。
- [ ] 两个不同技术栈的独立 MCP Server 成功接入。
- [ ] 新增 MCP Server 不需要修改 Hub Core 代码。
- [ ] 一个 Agent 可以组合调用两个不同服务。
- [ ] 工具标识唯一，冲突可检测并拦截。
- [ ] 无权限调用被明确拒绝，工具列表按用户权限隔离。
- [ ] 严禁客户端 Token 直接透传下游。
- [ ] 调用日志能够完整追踪客户端、用户、工具与执行结果。
- [ ] 服务故障不会造成虚假的成功反馈。
- [ ] Hub 能检测工具契约的不兼容变化。
- [ ] Docker Compose 离线镜像能够完整独立部署运行。
- [ ] TICM 真实查询结果通过业务数据一致性校验（P3）。
- [ ] 独立开发人员可以按照接入规范完成服务注册。

---

## 十、架构决策记录（ADR）清单

本项目关键技术决策均已规范化为独立 ADR 文档，存放在 `docs/adr/` 目录中：

| 编号 | 决策主题 | 核心内容摘要 | 决策文件 |
| :--- | :--- | :--- | :--- |
| **ADR-001** | Hub Core 技术栈与离线部署 | Python 3.11+, FastMCP, FastAPI, SQLite, Docker Compose 离线交付 | [ADR-001-技术栈与部署.md](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-001-技术栈与部署.md) |
| **ADR-002** | 聚合 MCP Server 模式与边界 | 对外单 MCP 端点，对内多 MCP Client；MVP 仅聚合 Tools | [ADR-002-聚合网关模式.md](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-002-聚合网关模式.md) |
| **ADR-003** | 无状态设计与旧版会话管理 | Hub 对外无状态（2026-07-28）；旧版下游由 Client 适配层管理 session | [ADR-003-Session管理.md](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-003-Session管理.md) |
| **ADR-004** | 身份认证与分阶段授权模型 | P0-P2 签名测试 JWT；P3 完成正式身份委托；严禁客户端 Token 透传 | [ADR-004-身份授权.md](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-004-身份授权.md) |
| **ADR-005** | 工具发现、变更审核与缓存 | 注册时发现、启动时校验、管理员刷新；按权限隔离；ttlMs=0, private | [ADR-005-工具发现与缓存.md](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-005-工具发现与缓存.md) |
| **ADR-006** | MCP 协议版本基线与兼容策略 | 以 2026-07-28 为首选基线；2025-11-25 条件兼容；旧版按需实测 | [ADR-006-协议版本兼容.md](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-006-协议版本兼容.md) |
| **ADR-007** | 聚合实现路径与退回预案 | P0 验证 FastMCP create_proxy+mount；设四项准入标准；不满足退回 mcp SDK | [ADR-007-聚合实现路径.md](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-007-聚合实现路径.md) |
| **ADR-008** | 服务发现响应规范 | server/discover 仅发布 Hub 自身能力；ttlMs=0, cacheScope=private | [ADR-008-服务发现响应.md](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-008-服务发现响应.md) |
| **ADR-009** | 端点路由架构与管理认证隔离 | /mcp 给 Harness，/api/v1 给管理员，/healthz 监控；同进程路由与认证分离 | [ADR-009-端点与管理接口.md](file:///c:/Users/chenfei/Desktop/workspace/aiprojects/ai-capability-hub/docs/adr/ADR-009-端点与管理接口.md) |

---

## 十一、明确暂不开发的内容

为避免过度设计，以下能力不进入第一阶段：

- 复杂 Web 前端管理后台（初期采用命令行或 REST API）。
- 企业级 MCP 应用市场与开发者广场。
- MCP Server 自动化代码生成平台。
- 多语言 Hub 专有 SDK。
- stdio 进程的自动容器化托管与桥接。
- 复杂的多级审批工作流引擎。
- 生产级全量身份管理与 SSO 平台（留待 P3 对接）。
- 分布式 Agent 协同与编排引擎。
- 高可用多活集群与分布式缓存。

---

## 十二、最终交付与原则总结

**项目核心原则：**

1. **业务能力独立于 Harness：** 接口契约面向业务抽象，不绑定任何特定 Agent 客户端。
2. **MCP Server 独立于 Hub：** 各业务服务独立开发、独立部署，不依赖 Hub 内部业务代码。
3. **开发规范独立于编程语言：** 业务服务自由选用 Python、Java、Go、Node.js 等技术栈。
4. **权限治理独立于大模型决策：** 严格由受控代码和传输层安全凭据判定权限，绝不相信 Prompt 参数。
5. **离线镜像保障内网交付：** 依赖前置固化，保障银行内网安全合规部署。
6. **架构演进保持渐进收敛：** 不为了形式上的架构完整性而提前建设过度复杂的中间件体系。
