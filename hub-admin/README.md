# hub-admin（已归档 · 停止独立部署）

> **状态说明**：原 `ai-capability-hub/hub-admin` 门户与治理控制台页面已完整迁移并合入 **`RgOne/frontend`**（`src/views/portal/CapabilitiesView.vue` 与 `src/views/admin/AdminMcpHubView.vue`）。
>
> 自前后端收口改造完成后：
> - **唯一前端入口**：统一由 `RgOne/frontend` 提供员工能力中心与管理员 MCP 治理台，共用 RgOne 原生小秘书/管理员登录态及 M3 设计体系。
> - **停止独立部署**：`ai-capability-hub/docker-compose.yml` 与离线镜像导出脚本已移除 `hub-admin` 服务，`ai-capability-hub` 作为纯无头下游 MCP 引擎（`hub-core`）运行。
> - **保留说明**：本目录暂保留作迁移参考归档，请勿在此目录继续开发新页面或重新启用独立容器。
