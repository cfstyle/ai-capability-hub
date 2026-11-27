# 网点运营助手 (branch-helper)

遵循 AI Capability Hub (ACH) 规范的演示 MCP 插件，包含：
- `query_exchange_rate`（L0 免参数）：查询模拟外汇牌价，上传发布后即可直接在线调试。
- `query_my_branch_quota`（L1 需个人参数透传）：读取 `branch_code` 与 `operator_token` 透传参数，用于验证个人参数绑定与后台「允许个人参数透传」开关。
