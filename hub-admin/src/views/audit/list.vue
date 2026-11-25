<template>
  <div class="audit-page">
    <div class="page-header">
      <div class="title-area">
        <h1 class="type-title-lg">调用日志与审计</h1>
        <p class="type-body text-secondary">全量追溯经由 Hub Gateway 调用的 MCP 工具操作、执行耗时与参数脱敏记录</p>
      </div>
      <MdButton variant="tonal" :disabled="loading" @click="fetchLogs">
        <RefreshCw :size="16" :class="{ 'is-spinning': loading }" />
        <span>刷新</span>
      </MdButton>
    </div>

    <!-- 单一完整卡片骨架 MdTable（筛选工具栏嵌入顶部，分页无缝融合在底栏） -->
    <MdTable
      :columns="columns"
      :data="logs"
      :loading="loading"
      :row-key="getAuditRowKey"
      empty-text="暂无调用审计记录"
      empty-description="当 AI Agent 或调试台发起工具调用时，审计日志将在此呈现"
    >
      <!-- 顶部工具栏（单行 36px 等高紧凑内联布局） -->
      <template #toolbar>
        <div class="filter-controls">
          <MdSelect
            v-model="filters.status"
            :options="statusOptions"
            prefix="执行状态："
            placeholder="全部状态"
            size="sm"
            style="min-width: 170px"
          />

          <MdInput
            v-model="filters.service_id"
            placeholder="按服务 ID 过滤"
            size="sm"
            clearable
            style="width: 160px"
          />

          <MdInput
            v-model="filters.tool_name"
            placeholder="按工具名称过滤"
            size="sm"
            clearable
            style="width: 160px"
          />
        </div>

        <div class="filter-actions">
          <MdButton variant="tonal" size="sm" @click="handleSearch">
            <Search :size="15" />
            <span>查询</span>
          </MdButton>
        </div>
      </template>

      <!-- 列插槽：调用时间 -->
      <template #cell-timestamp="{ row }">
        <span class="type-meta tabular-nums text-secondary">{{ formatTime(row.timestamp) }}</span>
      </template>

      <!-- 列插槽：服务 -->
      <template #cell-service_id="{ row }">
        <span class="chip-pill chip-inactive">{{ row.service_id }}</span>
      </template>

      <!-- 列插槽：工具 -->
      <template #cell-tool_name="{ row }">
        <span class="mono-code truncate max-w-[180px] block">{{ row.tool_name }}</span>
      </template>

      <!-- 列插槽：耗时 -->
      <template #cell-duration_ms="{ row }">
        <span class="type-meta tabular-nums mono-font font-medium">{{ row.duration_ms }} ms</span>
      </template>

      <!-- 列插槽：结果状态 -->
      <template #cell-result_status="{ row }">
        <span
          :class="[
            'chip-pill',
            row.result_status.includes('success') ? 'chip-active' : 'chip-error'
          ]"
        >
          {{ row.result_status }}
        </span>
      </template>

      <!-- 列插槽：调用主体 -->
      <template #cell-user_id="{ row }">
        <span class="type-meta text-secondary">{{ row.user_id || '-' }}</span>
      </template>

      <!-- 列插槽：脱敏入参摘要 (统一 truncate max-w-[260px] + MdTooltip) -->
      <template #cell-params_summary="{ row }">
        <MdTooltip :content="JSON.stringify(row.params_summary)" placement="top">
          <span class="mono-code truncate max-w-[260px] block cursor-help">
            {{ JSON.stringify(row.params_summary) }}
          </span>
        </MdTooltip>
      </template>

      <!-- 列插槽：详情查看 -->
      <template #cell-actions="{ row }">
        <div class="table-actions">
          <MdButton variant="text" size="sm" @click="viewDetail(row)">
            查看
          </MdButton>
        </div>
      </template>

      <!-- 底部分页插槽（一体化融合底栏） -->
      <template #pagination>
        <MdPagination
          :page="page"
          :page-size="pageSize"
          :total="total"
          :page-size-options="[10, 20, 50, 100]"
          @update:page="handlePageUpdate"
          @update:page-size="handlePageSizeUpdate"
        />
      </template>
    </MdTable>

    <!-- 审计明细模态框 (AdaptiveModal) -->
    <AdaptiveModal
      v-model="detailVisible"
      title="审计事件明细"
      width="640px"
    >
      <div class="audit-detail-grid" v-if="selectedLog">
        <div class="detail-row">
          <span class="type-meta text-secondary">事件时间</span>
          <span class="type-body tabular-nums">{{ selectedLog.timestamp }}</span>
        </div>
        <div class="detail-row">
          <span class="type-meta text-secondary">目标服务</span>
          <span class="mono-code">{{ selectedLog.service_id }}</span>
        </div>
        <div class="detail-row">
          <span class="type-meta text-secondary">工具名称</span>
          <span class="mono-code">{{ selectedLog.tool_name }}</span>
        </div>
        <div class="detail-row">
          <span class="type-meta text-secondary">调用主体</span>
          <span class="type-body">{{ selectedLog.user_id }} (客户端: {{ selectedLog.client_id }})</span>
        </div>
        <div class="detail-row">
          <span class="type-meta text-secondary">执行耗时</span>
          <span class="type-body mono-font font-medium">{{ selectedLog.duration_ms }} ms</span>
        </div>
        <div class="detail-row">
          <span class="type-meta text-secondary">执行状态</span>
          <span
            :class="[
              'chip-pill',
              selectedLog.result_status.includes('success') ? 'chip-active' : 'chip-error'
            ]"
          >
            {{ selectedLog.result_status }}
          </span>
        </div>
        <div class="detail-row full-width">
          <span class="type-meta text-secondary">脱敏参数 Payload</span>
          <pre class="m3-param-box"><code>{{ JSON.stringify(selectedLog.params_summary, null, 2) }}</code></pre>
        </div>
      </div>
      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="outlined" size="sm" @click="detailVisible = false">关闭</MdButton>
        </div>
      </template>
    </AdaptiveModal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { RefreshCw, Search } from 'lucide-vue-next'
import { listAuditLogs } from '@/api/audit'
import type { AuditLogItem } from '@/api/types'
import {
  MdTable,
  MdButton,
  MdPagination,
  MdSelect,
  MdInput,
  MdTooltip,
  AdaptiveModal,
  type SelectOption,
  type MdTableColumn,
} from '@/components/m3'

const columns: MdTableColumn<AuditLogItem>[] = [
  { key: 'timestamp', title: '调用时间', width: '170px' },
  { key: 'service_id', title: '服务', width: '120px' },
  { key: 'tool_name', title: '工具', width: '160px' },
  { key: 'duration_ms', title: '耗时', width: '90px', align: 'right', numeric: true },
  { key: 'result_status', title: '结果状态', width: '120px', align: 'center' },
  { key: 'user_id', title: '调用主体', width: '130px' },
  { key: 'params_summary', title: '脱敏入参摘要', width: '220px' },
  { key: 'actions', title: '操作', width: '80px', align: 'right' },
]

const statusOptions: SelectOption[] = [
  { label: '全部状态', value: '' },
  { label: '成功 (success)', value: 'success' },
  { label: '失败 (error)', value: 'error' },
  { label: '工具异常 (tool_error)', value: 'tool_error' },
]

const loading = ref(false)
const logs = ref<AuditLogItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = reactive({
  service_id: '',
  tool_name: '',
  status: '',
})

const detailVisible = ref(false)
const selectedLog = ref<AuditLogItem | null>(null)

function getAuditRowKey(log: AuditLogItem, idx: number): string | number {
  return log.id || idx
}

function formatTime(isoStr: string) {
  if (!isoStr) return '-'
  try {
    return new Date(isoStr).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return isoStr
  }
}

async function fetchLogs() {
  loading.value = true
  try {
    const res = await listAuditLogs({
      service_id: filters.service_id.trim() || undefined,
      tool_name: filters.tool_name.trim() || undefined,
      status: filters.status || undefined,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    logs.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchLogs()
}

function handlePageUpdate(newPage: number) {
  page.value = newPage
  fetchLogs()
}

function handlePageSizeUpdate(newSize: number) {
  pageSize.value = newSize
  page.value = 1
  fetchLogs()
}

function viewDetail(log: AuditLogItem) {
  selectedLog.value = log
  detailVisible.value = true
}

onMounted(() => {
  fetchLogs()
})
</script>

<style scoped>
.audit-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-area {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.text-secondary {
  color: var(--md-sys-color-on-surface-variant);
}

.is-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.filter-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-actions {
  display: flex;
  align-items: center;
  margin-left: auto;
}

.mono-font {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.mono-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-block;
  line-height: 1.4;
}

.chip-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--md-sys-shape-corner-full, 9999px);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
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

.chip-error {
  background-color: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.table-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
}

/* Detail Modal */
.audit-detail-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 8px 0;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  background-color: transparent;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.detail-row.full-width {
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  border-bottom: none;
  padding-top: 14px;
}

.m3-param-box {
  width: 100%;
  background-color: var(--md-sys-color-surface-container-highest);
  color: var(--md-sys-color-on-surface);
  padding: 12px;
  border-radius: var(--md-sys-shape-corner-small, 8px);
  border: 1px solid var(--md-sys-color-outline-variant);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  max-height: 260px;
  overflow: auto;
  box-sizing: border-box;
}

.modal-footer-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
