# AI Capability Hub V0.2.2：二轮评审回复与实施决策

我建议采纳本轮评审的总体方向，并将部署方式正式确定为 Docker Compose。其余三个红色问题都可以给出明确答案，不必再让开发团队自行猜测。

不过，这次核对官方文档后，我发现一个需要特别纠正的技术细节：

独立的 FastMCP 框架与 MCP 官方 Python SDK 2.x 不是同一个项目。

- `fastmcp`：独立框架，提供 `create_proxy()`、`mount()`、Middleware、Provider 等高级能力。
- `mcp`：MCP 官方 Python SDK，2.x 中主要的高级服务类已更名为 `MCPServer`。

因此，不能直接认定官方 `mcp` SDK 2.x 自带评审报告中提到的 `create_proxy + mount` 完整聚合机制。

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+2



这是本轮需要正式记录的技术风险。

## 一、三个红色问题的最终答复

### ADR-007：聚合代理实现路线

决定：P0 优先验证 FastMCP `create_proxy + mount`，不直接自研完整 MCP 协议代理。

FastMCP 的官方文档已经确认：

- 可以把远程 MCP Server 转换为代理。
- 可以把多个代理挂载到一个聚合 Server。
- 可以使用 Namespace 区分不同服务。
- 父级 Middleware 可以拦截挂载子服务的工具调用。

因此，评审方提出的方案 A 在功能上有明确基础。

[image](https://www.google.com/s2/favicons?domain=https://gofastmcp.com\&sz=32)

FastMCP+1



但我不会直接把它定为最终生产框架。

因为我们还需要确认它能否满足 Hub 最重要的四个要求：

| 验证内容 | 必须达到的效果                 |
| ---- | ----------------------- |
| 工具发现 | 可按用户权限过滤 Tool List      |
| 工具执行 | 每次调用必须经过独立授权和审计         |
| 动态接入 | 新增 MCP Server 不需要修改核心代码 |
| 身份隔离 | 不同用户调用下游服务时不会混用凭证或身份    |

尤其需要关注：FastMCP Proxy 的文档说明，部分版本默认会转发符合条件的入站 HTTP Header，包括 `Authorization`。银行 Hub 不能默认把客户端令牌转发给下游 MCP Server，必须显式禁用这种行为，改用受控的下游授权机制。

[image](https://www.google.com/s2/favicons?domain=https://gofastmcp.com\&sz=32)

FastMCP



我建议采用明确的决策门槛：

- 如果 FastMCP 能满足四项要求，正式采用 FastMCP。
- 如果功能可以满足，但需要少量适配，则开发受控的扩展层。
- 如果授权、动态注册或隔离机制无法可靠保证，则退回官方 `mcp` SDK 2.x 的 Server/Client API 实现自定义聚合层。

无论选择哪条路线，Registry、Governance 和路由配置都必须由 Hub 自己定义，不允许与 FastMCP 的内部对象深度绑定。

这样即使未来更换聚合框架，也不会推翻能力注册、权限策略和业务服务。

### ADR-008：`server/discover` 响应

决定：Hub 只发布自身能力，不汇总下游 Server 的发现信息。

按照 MCP `2026-07-28` 规范，`server/discover` 是服务端必须实现的方法，但客户端不一定每次都调用。其结果包含协议版本、能力声明、服务器信息和缓存控制。

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub



建议采用以下配置：

| 字段                  | MVP 决策                        |
| ------------------- | ----------------------------- |
| `supportedVersions` | 仅列出 Hub 实际支持的新版协议版本           |
| `capabilities`      | 只声明 `tools`                   |
| `serverInfo`        | Hub 自身名称和版本，放在协议规定的 `_meta` 中 |
| `instructions`      | 使用 Hub 自己维护的静态说明              |
| `ttlMs`             | `0`                           |
| `cacheScope`        | `private`                     |
| `resultType`        | `complete`                    |

其中有两个重要约束：

第一，`supportedVersions` 不能简单把所有下游服务支持的版本合并起来。它表示的是 Hub 对外支持的协议版本。

第二，暂不声明 `tools.listChanged` 主动通知能力。工具列表变化后，由客户端重新查询。后续如果实现 `subscriptions/listen`，再正式启用相关能力。

`ttlMs=0` 和 `cacheScope=private` 也与官方 Python SDK 的安全默认值一致，适合初期权限与工具列表可能发生变化的情况。

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub



### ADR-009：管理 API 与 MCP 端点

决定：MVP 同一容器、同一应用进程、不同路由、不同认证机制。

| 路由          | 用途                | 认证         |
| ----------- | ----------------- | ---------- |
| `/mcp`      | Harness 调用 MCP 工具 | 客户端及用户授权令牌 |
| `/api/v1/*` | 注册、更新、禁用、刷新服务     | 管理员令牌      |
| `/healthz`  | 进程存活检查            | 容器内部       |
| `/readyz`   | Hub 就绪检查          | 内部监控       |

注意：路由分离不等于安全隔离。

即使运行在同一个进程中，管理接口也应受到额外的网络访问限制，不能因为知道 Hub 的地址就能够注册新的 MCP Server。

第一版不需要引入复杂的企业 SSO，但测试令牌应有独立的签发、验证及权限范围，不能把一个管理员 API Key 同时用于工具调用。

以后如果管理后台规模扩大，可以再把管理 API 和 MCP Gateway 拆成独立服务，而无需改变外部 API 契约。

## 二、五项实施风险的处理决定

| 评审项              | V0.2.2 决策                      | 实施阶段 |
| ---------------- | ------------------------------ | ---- |
| 4. SDK 与离线安装     | Docker Compose + 离线镜像交付，锁定完整依赖 | P0   |
| 5. 下游连接生命周期      | 复用 HTTP 连接池，独立管理下游连接状态         | P1   |
| 6. DeepSeek 协议兼容 | 允许客户端使用经过测试的旧版协议               | P0   |
| 7. P0 范围过大       | 接受评审意见，恢复为最小协议验证               | P0   |
| 8. 工具变更通知        | MVP 不实现主动通知，提供手动刷新             | P1   |

### 1. 离线部署正式采用 Docker Compose

这个方案适合当前的银行内网环境。

我建议第一版部署结构如下：

DeepSeek Harness / 其他客户端

内网访问 Hub 的 MCP 地址

Docker Compose 应用栈

hub-core

Registry · Gateway · Governance · 管理 API

ticm-mcp

Python 示例

message-mcp

Node.js 示例

持久化 Volume：SQLite · 注册配置 · 审计日志

部署要求：

- 在可访问依赖仓库的受控构建环境中构建镜像。
- 锁定 SDK 和依赖版本，生成软件物料清单（SBOM）及镜像摘要。
- 将完整镜像导出，经过安全检查后导入隔离内网。
- 使用 Docker Compose 启动所有服务，禁止部署时自动从外网拉取镜像。
- SQLite、配置及日志使用持久化卷。
- 只有 Hub 对客户端提供访问入口，下游 MCP Server 默认仅在内部网络可达。
- 通过 Compose Healthcheck 判断服务健康，并启用适当的重启策略。

首版使用 SQLite 没问题。它的写入并发和备份机制要受到控制；未来若出现多实例部署需求，再考虑 PostgreSQL。

不建议内网启动时临时 `pip install`。 最终交付应该是已经包含依赖的镜像，而不是让生产服务器现场下载或编译软件包。

还有一点：FastMCP 的独立版本和官方 `mcp` SDK 的版本不能机械组合。应先在 P0 确认兼容性，再锁定经过验证的实际版本与镜像摘要。

### 2. 下游连接池和动态注册

我建议：

连接管理由 MCP Client/Transport 层负责，Registry 只负责服务元数据。

这样动态注册 MCP Server 时，不需要直接修改 Gateway 的业务逻辑。

具体设计：

- HTTP 连接由客户端传输层管理和复用。
- 下游服务不可用时，允许连接重新建立。
- 每个服务拥有独立的连接配置和超时策略。
- 不共享不同用户的认证上下文。
- 运行中新增、停用服务通过 Registry 管理。

但是 FastMCP 的 `mount()` 虽然支持动态组合，不等于我们已经验证了生产状态下随时新增、删除远程服务的全部生命周期行为。特别是服务注册持久化、并发刷新及工具缓存更新，还需自行验证。

[image](https://www.google.com/s2/favicons?domain=https://gofastmcp.com\&sz=32)

FastMCP



所以我建议 P1 先允许新增服务后进行受控配置刷新。

运行中无需重启的热插拔能力，可以在 P2 验证后正式纳入支持范围。

### 3. DeepSeek Harness 的兼容性

我赞成评审方提出的降级预案。

如果现有 DeepSeek Harness 只兼容旧版 MCP：

Hub 的对外协议适配到客户端可用的版本，内部仍保持统一的业务执行与治理模型。

但还要增加一个限制：

不能假设新版无状态模式可以自动代理所有旧版有状态能力。

P0 重点测试 `tools/list`、`tools/call` 和必要的初始化流程。旧版下游的会话生命周期由适配层处理。

如果 DeepSeek Harness 不支持 Authorization Header，应在 P0 记录这一限制，可以先使用隔离的模拟测试环境验证协议；真实用户业务接入必须另行建立可信身份机制，不能用共享高权限账号代替。

### 4. 重新调整 P0 的边界

这一点我同意二轮评审。

上一轮确实把 P1、P2 的一部分验收提前放进 P0 了。

现在正式调整：

P0 唯一核心目标

证明选定的聚合代理技术路线，在目标 Harness 上可以完成标准 MCP 工具调用。

最小测试组合

DeepSeek Harness

Hub

Mock MCP

通过 `tools/list` 和 `tools/call`，验证协议兼容、代理路由与基本返回结果。

工具级权限、多服务聚合和动态注册放到 P1、P2 验证。

不过 FastMCP 父级 Middleware 能否拦截代理后的工具调用，可以在 P0 顺手做一个最小可行性测试，因为这直接影响是否选择 FastMCP 作为长期技术基础。

### 5. 工具动态上下线通知

MCP `2026-07-28` 仍支持 `notifications/tools/list_changed`，但需要客户端通过 `subscriptions/listen` 订阅，而不是服务端无条件主动推送。

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub



MVP 不实现这一机制。

先支持管理员刷新和客户端重新获取工具列表。

如果发生权限撤销，Hub 必须在实际执行前重新校验授权，即使 Harness 仍然缓存着旧的工具清单，也不能继续执行已经被撤销权限的调用。

## 三、其余两项文档建议：全部采纳

我建议将技术设计文档组织成下面这样的结构。

```

docs/
├── 企业级AI业务能力中心-总体方案.md
├── 架构设计.md
├── MCP-Server接入规范.md
├── 安全与权限设计.md
├── 测试与验收规范.md
└── adr/
    ├── ADR-001-技术栈与部署.md
    ├── ADR-002-聚合网关模式.md
    ├── ADR-003-Session管理.md
    ├── ADR-004-身份授权.md
    ├── ADR-005-工具发现与缓存.md
    ├── ADR-006-协议版本兼容.md
    ├── ADR-007-聚合实现路径.md
    ├── ADR-008-服务发现响应.md
    └── ADR-009-端点与管理接口.md
  
```

每份 ADR 使用相同结构：

背景（Context）→ 决策（Decision）→ 影响（Consequences）→ 状态（Status）。

同时将总体方案升级为 V0.2.2，文档中只保留当前有效的技术决策，并通过 ADR 引用说明理由。

避免后续开发时出现 V0.2、V0.2.1、V0.2.2 三份方案互相矛盾。

## 四、交给开发方的最终执行指令

# AI Capability Hub V0.2.2 — 二轮评审执行要求

请根据 V0.2 总体方案及 V0.2.1 修订决策，完成以下 V0.2.2 架构调整。

## 1. 技术路线

- Hub Core 使用 Python 3.11+。
- 优先验证独立 FastMCP 的 `create_proxy + mount + middleware` 方案。
- 明确区分独立 `fastmcp` 框架与官方 `mcp` SDK 2.x。
- FastMCP 如不能满足工具授权、调用审计、身份隔离和动态注册要求，则退回官方 MCP SDK 2.x 自定义聚合实现。
- 不允许业务层代码直接依赖具体聚合框架内部接口。

## 2. 部署

- 全部采用 Docker Compose。
- 在受控联网环境构建镜像，隔离内网离线导入。
- 固定依赖版本、保存依赖锁文件及镜像摘要。
- Hub、TICM Mock MCP、第二个 Mock MCP 独立容器化。
- SQLite 和日志持久化。
- 下游 MCP Server 不直接暴露给普通客户端。

## 3. 聚合网关

- 对外表现为一个聚合 MCP Server。
- 对内作为多个 MCP Server 的 Client。
- MVP 只支持 Tools。
- 提供 `tools/list` 聚合、`tools/call` 授权与路由。
- 提供稳定命名空间及唯一性检查。
- 不允许将客户端 Authorization Token 无条件透传给下游服务。
- 所有工具执行经过统一治理逻辑。

## 4. 协议及缓存

- 优先支持 MCP `2026-07-28`。
- 根据实际测试支持必要的旧版协议。
- 正确实现相应版本的发现及初始化流程。
- 新版 `server/discover` 只声明 Hub 自身能力。
- 初期使用 `ttlMs=0`、`cacheScope=private`。
- 不汇总下游 Server Instructions。
- 首版不支持主动工具变更通知及长时间流式任务。

## 5. 管理接口

- `/mcp`：Harness 调用。
- `/api/v1/*`：管理及注册操作。
- `/healthz`、`/readyz`：健康检查。
- MCP 与管理 API 使用独立权限策略。
- 管理 API 仅向授权管理员开放。

## 6. P0 验证

采用一个 Harness、一个 Hub、一个 Mock MCP Server。

验证：

- MCP 协议初始化或服务发现。
- `tools/list`。
- `tools/call`。
- 代理后的正确响应。
- FastMCP Middleware 对工具列表和实际调用的拦截能力。
- 目标 Harness 的协议版本及认证支持。
- Docker Compose 离线镜像部署。

P0 不要求完整权限平台、不要求真实 TICM 数据，也不要求两个下游服务聚合。

## 7. P1、P2 验证

P1 实现 Registry、Gateway、测试身份授权及基础审计。

P2 接入第二个独立技术栈的 MCP Server，验证工具聚合、命名冲突、异常处理、动态注册和服务更新。

两阶段均以独立服务接入为原则，不允许通过复制业务代码到 Hub 内部的方式绕过插件机制。

## 8. 开发文档

- 将总体方案更新到 V0.2.2。
- 将 ADR-001 至 ADR-009 规范化。
- 补充部署架构图、调用时序图和注册流程图。
- 在 P0 完成后，记录实际锁定的 SDK 版本与兼容矩阵。
- 清理旧版本中与新决策相冲突的描述。

## 9. 安全底线

- 不允许匿名调用真实银行敏感业务工具。
- 不允许未经校验的身份参数决定业务数据权限。
- 不允许跨用户共享访问凭据或会话状态。
- 未通过安全及兼容测试的第三方 MCP 不允许正式发布。
- 生产环境的写操作必须执行经批准的业务授权与风险控制。

最终交付以协议兼容性、独立服务接入、统一授权及跨语言扩展能力为核心，不以管理界面丰富程度或预置工具数量作为验收依据。

## 五、这次评审之后，是否可以正式开工？

可以，而且我认为现在应该停止继续扩大架构设计范围。

目前真正需要通过开发验证的只剩下两个核心不确定性：

第一个：FastMCP 能否在代理其他 MCP Server 的同时，可靠地实现我们需要的统一治理。

这是决定 Hub 底层技术选型的关键。官方文档已确认代理、挂载及父级 Middleware 具备基础能力，但我们的身份隔离、工具过滤和动态注册组合仍需要实测。

[image](https://www.google.com/s2/favicons?domain=https://gofastmcp.com\&sz=32)

FastMCP+2



第二个：DeepSeek Harness 能否按照我们选择的协议与 Hub 正常通信。

如果 P0 成功，这两个问题就基本得到解决。接下来可以按照既定路线实施 Registry、Gateway、多服务接入以及 TICM 业务能力。

我的建议是将 V0.2.2 作为 P0 的执行基线，而不是继续等待一份在纸面上完全没有疑问的设计方案。

后续开发遇到真实的 SDK 限制或协议问题，再通过 ADR 修订对应决策，而不推翻“开放 Hub + 独立 MCP Server + 统一治理”的总体架构。