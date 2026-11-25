<template>
  <div class="dashboard-page">
    <!-- 页面标题与刷新按钮 -->
    <div class="page-header">
      <div>
        <h1 class="type-title-lg">运行总览</h1>
        <p class="type-body-sm text-secondary">实时掌控 MCP Server 节点、工具注册表及核心网关指标</p>
      </div>
      <MdButton
        variant="tonal"
        class="refresh-btn"
        :disabled="loading"
        @click="fetchData"
      >
        <RefreshCw :size="16" :class="{ 'is-spinning': loading }" />
        <span>刷新状态</span>
      </MdButton>
    </div>

    <!-- 4 大核心指标卡片 -->
    <div class="metrics-grid">
      <!-- 指标 1: 已注册 MCP Server -->
      <MdCard variant="elevated" class="metric-card">
        <div class="metric-top">
          <span class="metric-label type-body-sm">已注册 MCP Server</span>
          <div class="metric-icon-box bg-primary-container text-on-primary-container">
            <Server :size="20" />
          </div>
        </div>
        <div class="metric-value type-display">{{ summary.servers_total }}</div>
        <div class="metric-footer type-body-sm">
          <span class="status-chip success">正常: {{ summary.servers_active }}</span>
          <span class="status-chip warning" v-if="summary.servers_inactive > 0">停用: {{ summary.servers_inactive }}</span>
          <span class="status-chip error" v-if="summary.servers_degraded > 0">降级: {{ summary.servers_degraded }}</span>
        </div>
      </MdCard>

      <!-- 指标 2: 已发现工具总数 -->
      <MdCard variant="elevated" class="metric-card">
        <div class="metric-top">
          <span class="metric-label type-body-sm">已发现工具 (Tools)</span>
          <div class="metric-icon-box bg-secondary-container text-on-secondary-container">
            <Wrench :size="20" />
          </div>
        </div>
        <div class="metric-value type-display">{{ summary.tools_total }}</div>
        <div class="metric-footer type-body-sm text-secondary">
          来自全量已挂载 MCP 服务能力契约
        </div>
      </MdCard>

      <!-- 指标 3: 控制面就绪状态 -->
      <MdCard variant="elevated" class="metric-card">
        <div class="metric-top">
          <span class="metric-label type-body-sm">控制面状态</span>
          <div class="metric-icon-box bg-tertiary-container text-on-tertiary-container">
            <Activity :size="20" />
          </div>
        </div>
        <div class="metric-value status-indicator">
          <span
            :class="[
              'status-badge',
              hubStatus.status === 'ready' || hubStatus.status === 'ok' ? 'is-ready' : 'is-error'
            ]"
          >
            {{ hubStatus.status.toUpperCase() }}
          </span>
        </div>
        <div class="metric-footer type-body-sm text-secondary">
          Hub Core v{{ hubStatus.hub_version }} · {{ hubStatus.database }}
        </div>
      </MdCard>

      <!-- 指标 4: 网关调用与安全性 -->
      <MdCard variant="elevated" class="metric-card">
        <div class="metric-top">
          <span class="metric-label type-body-sm">调用网关审计</span>
          <div class="metric-icon-box bg-surface-highest text-primary">
            <ShieldCheck :size="20" />
          </div>
        </div>
        <div class="metric-value type-display">
          <span v-if="summary.calls_total !== undefined">{{ summary.calls_total }}</span>
          <span v-else class="text-secondary text-base">自动审计就绪</span>
        </div>
        <div class="metric-footer type-body-sm text-secondary">
          完整记录 trace_id、耗时与参数脱敏
        </div>
      </MdCard>
    </div>

    <!-- 下半部：服务实时状态列表 + 快速入口 -->
    <div class="content-grid">
      <!-- 左侧：服务列表 MdTable (单一完整卡片骨架) -->
      <MdTable
        :columns="dashboardColumns"
        :data="services"
        :loading="loading"
        row-key="id"
        empty-text="暂无已注册服务"
        empty-description="点击右侧注册新 MCP Server 开始接入"
      >
        <template #toolbar>
          <div>
            <h2 class="type-title-md font-semibold text-on-surface">已注册服务实时状态</h2>
            <span class="type-meta text-secondary">最近接入的远程 MCP Server 运行健康度</span>
          </div>
          <MdButton variant="text" size="sm" @click="$router.push('/servers/list')">
            <span>查看全部</span>
            <ExternalLink :size="14" />
          </MdButton>
        </template>

        <template #cell-id="{ row }">
          <span class="mono-code">{{ row.id }}</span>
        </template>

        <template #cell-name="{ row }">
          <span class="type-body font-medium">{{ row.name }}</span>
        </template>

        <template #cell-endpoint_url="{ row }">
          <MdTooltip :content="row.endpoint_url" placement="top">
            <span class="mono-code truncate max-w-[200px] block cursor-help">{{ row.endpoint_url }}</span>
          </MdTooltip>
        </template>

        <template #cell-status="{ row }">
          <span
            :class="[
              'chip-pill',
              row.status === 'active' ? 'chip-active' : row.status === 'inactive' ? 'chip-inactive' : 'chip-degraded'
            ]"
          >
            {{ row.status }}
          </span>
        </template>

        <template #cell-owner="{ row }">
          <span class="type-meta text-secondary">{{ row.owner || '-' }}</span>
        </template>

        <template #cell-actions="{ row }">
          <MdButton variant="text" size="sm" @click="$router.push(`/servers/${row.id}`)">
            详情
          </MdButton>
        </template>
      </MdTable>

      <!-- 右侧：快捷入口 -->
      <MdCard variant="elevated" class="quick-card">
        <div class="card-header">
          <h2 class="type-title-md">快速入口</h2>
          <span class="type-body-sm text-secondary">高频运维与调试动作</span>
        </div>

        <div class="quick-links">
          <div class="quick-item md-state-layer" @click="$router.push('/servers/register')">
            <div class="quick-icon-box bg-primary-container text-on-primary-container">
              <Plus :size="20" />
            </div>
            <div class="quick-text">
              <div class="quick-title label-large">注册新 MCP Server</div>
              <div class="quick-desc body-small">录入远程 Streamable HTTP 地址并自动拉取 tools/list</div>
            </div>
          </div>

          <div class="quick-item md-state-layer" @click="$router.push('/tools/debug')">
            <div class="quick-icon-box bg-secondary-container text-on-secondary-container">
              <PlayCircle :size="20" />
            </div>
            <div class="quick-text">
              <div class="quick-title label-large">在线调试台</div>
              <div class="quick-desc body-small">基于 Input Schema 动态渲染表单受控测试执行</div>
            </div>
          </div>

          <div class="quick-item md-state-layer" @click="$router.push('/tools/list')">
            <div class="quick-icon-box bg-tertiary-container text-on-tertiary-container">
              <Layers :size="20" />
            </div>
            <div class="quick-text">
              <div class="quick-title label-large">工具契约目录</div>
              <div class="quick-desc body-small">查看全平台挂载的工具契约、风险级别与授权策略</div>
            </div>
          </div>

          <div class="quick-item md-state-layer" @click="$router.push('/system')">
            <div class="quick-icon-box bg-surface-highest text-primary">
              <Activity :size="20" />
            </div>
            <div class="quick-text">
              <div class="quick-title label-large">系统状态探针</div>
              <div class="quick-desc body-small">检查 /healthz 存活探针与 /readyz 就绪探针</div>
            </div>
          </div>
        </div>
      </MdCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  RefreshCw,
  Server,
  Wrench,
  Activity,
  ShieldCheck,
  ExternalLink,
  Plus,
  PlayCircle,
  Layers
} from 'lucide-vue-next'
import { MdCard, MdButton, MdTable, MdTooltip, type MdTableColumn } from '@/components/m3'
import { getDashboardSummary, getSystemStatus } from '@/api/system'
import { listServices } from '@/api/server'
import type { DashboardSummary, RegisteredService, SystemStatus } from '@/api/types'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const loading = ref(false)

const dashboardColumns: MdTableColumn<RegisteredService>[] = [
  { key: 'id', title: 'Service ID', width: '130px' },
  { key: 'name', title: '服务名称', width: '160px' },
  { key: 'endpoint_url', title: 'MCP Endpoint', width: '210px' },
  { key: 'status', title: '状态', width: '90px', align: 'center' },
  { key: 'owner', title: '维护人', width: '110px' },
  { key: 'actions', title: '操作', width: '80px', align: 'right' },
]

const summary = ref<DashboardSummary>({
  servers_total: 0,
  servers_active: 0,
  servers_inactive: 0,
  servers_degraded: 0,
  tools_total: 0,
})

const hubStatus = ref<SystemStatus>({
  hub_name: 'AI Capability Hub',
  hub_version: '0.3.0',
  status: 'ok',
  database: 'hub.db',
  mcp_endpoint: '/mcp',
  upstream_services_count: 0,
})

const services = ref<RegisteredService[]>([])

async function fetchData() {
  loading.value = true
  try {
    const [sum, stat, svcs] = await Promise.all([
      getDashboardSummary(),
      getSystemStatus(),
      listServices(undefined, { silent: true }),
    ])
    summary.value = sum
    hubStatus.value = stat
    services.value = svcs
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`获取运行状态失败: ${error.message || '网络异常'}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.text-secondary {
  color: var(--md-sys-color-on-surface-variant);
}

.text-primary {
  color: var(--md-sys-color-primary);
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
}

.is-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 4 格指标栅格 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

@media (max-width: 1024px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}

.metric-card {
  padding: 20px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border-radius: var(--md-sys-shape-corner-medium, 16px);
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.metric-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.metric-label {
  color: var(--md-sys-color-on-surface-variant);
  font-weight: 500;
}

.metric-icon-box {
  width: 38px;
  height: 38px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.bg-primary-container {
  background-color: var(--md-sys-color-primary-container);
}
.text-on-primary-container {
  color: var(--md-sys-color-on-primary-container);
}

.bg-secondary-container {
  background-color: var(--md-sys-color-secondary-container);
}
.text-on-secondary-container {
  color: var(--md-sys-color-on-secondary-container);
}

.bg-tertiary-container {
  background-color: var(--md-sys-color-tertiary-container);
}
.text-on-tertiary-container {
  color: var(--md-sys-color-on-tertiary-container);
}

.bg-surface-highest {
  background-color: var(--md-sys-color-surface-container-highest);
}

.metric-value {
  margin: 12px 0 8px 0;
  color: var(--md-sys-color-on-surface);
}

.text-base {
  font-size: 16px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: var(--md-sys-shape-corner-full);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.status-badge.is-ready {
  background-color: color-mix(in srgb, #198754 12%, var(--md-sys-color-surface));
  color: #198754;
  border: 1px solid color-mix(in srgb, #198754 25%, transparent);
}

.status-badge.is-error {
  background-color: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.metric-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.status-chip {
  padding: 2px 8px;
  border-radius: var(--md-sys-shape-corner-small, 6px);
  font-size: 12px;
  font-weight: 500;
}

.status-chip.success {
  background-color: color-mix(in srgb, #198754 12%, var(--md-sys-color-surface));
  color: #198754;
}

.status-chip.warning {
  background-color: color-mix(in srgb, #f59e0b 12%, var(--md-sys-color-surface));
  color: #b45309;
}

.status-chip.error {
  background-color: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
}

/* 内容布局栅格 */
.content-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
}

@media (max-width: 1024px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}

.table-card,
.quick-card {
  padding: 24px;
  border-radius: var(--md-sys-shape-corner-medium, 16px);
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.table-container {
  overflow-x: auto;
}

.chip-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--md-sys-shape-corner-full);
  font-size: 12px;
  font-weight: 600;
}

.chip-active {
  background-color: color-mix(in srgb, #198754 12%, var(--md-sys-color-surface));
  color: #198754;
  border: 1px solid color-mix(in srgb, #198754 25%, transparent);
}

.chip-inactive {
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-outline);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.chip-degraded {
  background-color: color-mix(in srgb, #f59e0b 12%, var(--md-sys-color-surface));
  color: #b45309;
  border: 1px solid color-mix(in srgb, #f59e0b 25%, transparent);
}

/* 快速操作列表 */
.quick-links {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.quick-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  border-radius: var(--md-sys-shape-corner-medium, 16px);
  background-color: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
  transition: transform var(--md-sys-motion-duration-short3) var(--md-sys-motion-easing-standard),
              border-color var(--md-sys-motion-duration-short3) var(--md-sys-motion-easing-standard);
}

.quick-item:hover {
  transform: translateY(-2px);
  border-color: var(--md-sys-color-primary);
}

.quick-icon-box {
  width: 44px;
  height: 44px;
  border-radius: var(--md-sys-shape-corner-small, 10px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.quick-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.quick-title {
  color: var(--md-sys-color-on-surface);
  font-weight: 600;
}

.quick-desc {
  color: var(--md-sys-color-on-surface-variant);
  line-height: 1.4;
}
</style>
