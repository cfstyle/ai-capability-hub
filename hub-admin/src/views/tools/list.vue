<template>
  <div class="tool-list-page">
    <!-- 头部区域 -->
    <div class="page-header">
      <div class="title-area">
        <h1 class="type-title-lg">工具目录管理</h1>
        <p class="type-body text-secondary">统一发现并治理已挂载各 MCP Server 对外开放的业务能力契约</p>
      </div>
      <MdButton variant="tonal" @click="$router.push('/tools/debug')">
        <PlayCircle :size="18" />
        <span>打开在线调试台</span>
      </MdButton>
    </div>

    <!-- 单一完整卡片骨架 MdTable（筛选栏内嵌于卡片顶部，无缝衔接表头） -->
    <MdTable
      :columns="columns"
      :data="filteredTools"
      :loading="loading"
      :row-key="getToolRowKey"
      empty-text="暂无匹配的业务工具"
      empty-description="请调整上方服务或风险等级筛选条件"
    >
      <!-- 顶部工具栏（单行 36px 等高紧凑内联布局） -->
      <template #toolbar>
        <div class="filter-controls">
          <MdSelect
            v-model="filters.service_id"
            :options="serviceOptions"
            prefix="所属服务："
            placeholder="全部服务"
            size="sm"
            style="min-width: 190px"
            @change="fetchTools"
          />

          <MdSelect
            v-model="filters.risk_level"
            :options="riskOptions"
            prefix="风险等级："
            placeholder="全部等级"
            size="sm"
            style="min-width: 160px"
          />

          <MdInput
            v-model="filters.keyword"
            placeholder="按工具名、描述搜索"
            size="sm"
            clearable
            style="width: 240px"
          >
            <template #prefix>
              <Search :size="15" class="text-secondary" />
            </template>
          </MdInput>
        </div>

        <div class="filter-actions">
          <MdButton variant="tonal" size="sm" :disabled="loading" @click="fetchTools">
            <RefreshCw :size="15" :class="{ 'is-spinning': loading }" />
            <span>刷新</span>
          </MdButton>
        </div>
      </template>

      <!-- 列插槽：工具名称 -->
      <template #cell-name="{ row }">
        <span class="mono-code truncate max-w-[160px] block">{{ row.name }}</span>
      </template>

      <!-- 列插槽：命名空间全称 -->
      <template #cell-namespace_name="{ row }">
        <span class="mono-code truncate max-w-[220px] block">{{ row.namespace_name || `${row.service_id}__${row.name}` }}</span>
      </template>

      <!-- 列插槽：所属服务 -->
      <template #cell-service_id="{ row }">
        <span class="chip-pill chip-inactive">{{ row.service_id }}</span>
      </template>

      <!-- 列插槽：业务说明单行截断 (统一 truncate max-w-[260px] + MdTooltip) -->
      <template #cell-description="{ row }">
        <MdTooltip v-if="row.description" :content="row.description" placement="top">
          <span class="type-body text-secondary truncate max-w-[260px] block cursor-help">
            {{ row.description }}
          </span>
        </MdTooltip>
        <span v-else class="text-secondary type-meta">-</span>
      </template>

      <!-- 列插槽：风险等级 -->
      <template #cell-risk_level="{ row }">
        <span :class="['risk-chip', `risk-${row.risk_level.toLowerCase()}`]">
          {{ row.risk_level }}
        </span>
      </template>

      <!-- 列插槽：人工确认 -->
      <template #cell-requires_confirmation="{ row }">
        <span :class="['chip-pill', row.requires_confirmation ? 'chip-warning' : 'chip-inactive']">
          {{ row.requires_confirmation ? '必需' : '免确认' }}
        </span>
      </template>

      <!-- 列插槽：精简操作列（保留主操作 + 更多操作） -->
      <template #cell-actions="{ row }">
        <div class="table-actions">
          <MdButton variant="text" size="sm" @click="goToDebug(row)">
            <Terminal :size="14" />
            <span>调试</span>
          </MdButton>

          <MdDropdown :items="getToolActions(row)" placement="bottom-end" />
        </div>
      </template>
    </MdTable>

    <!-- 治理策略弹窗 (AdaptiveModal) -->
    <AdaptiveModal
      v-model="policyDialogVisible"
      :title="`治理策略配置: ${policyTool?.name}`"
      width="520px"
    >
      <div class="m3-modal-form">
        <div class="form-row">
          <label class="type-meta text-secondary">所属服务</label>
          <div><span class="chip-pill chip-inactive">{{ policyTool?.service_id }}</span></div>
        </div>

        <div class="form-row">
          <label class="type-meta text-secondary">工具全称</label>
          <div><span class="mono-code">{{ policyTool?.namespace_name || `${policyTool?.service_id}__${policyTool?.name}` }}</span></div>
        </div>

        <div class="form-row">
          <label class="type-meta" for="policy-risk">风险等级 *</label>
          <MdSelect
            id="policy-risk"
            :model-value="policyForm.risk_level"
            :options="policyRiskOptions"
            placeholder="请选择风险等级"
            @update:model-value="(val) => (policyForm.risk_level = val as ToolRiskLevel)"
          />
        </div>

        <div class="form-row flex-row">
          <div class="switch-info">
            <span class="type-body font-medium">人工确认防线</span>
            <span class="type-meta text-secondary">开启后，调试台与网关将要求明确的人工授权确认才允许执行</span>
          </div>
          <MdSwitch
            :model-value="policyForm.requires_confirmation"
            @update:model-value="policyForm.requires_confirmation = $event"
          />
        </div>
      </div>

      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="text" size="sm" @click="policyDialogVisible = false">取消</MdButton>
          <MdButton variant="tonal" size="sm" :disabled="savingPolicy" @click="handleSavePolicy">
            <span v-if="!savingPolicy">保存策略</span>
            <span v-else>正在保存...</span>
          </MdButton>
        </div>
      </template>
    </AdaptiveModal>

    <!-- Schema 弹窗 (AdaptiveModal) -->
    <AdaptiveModal
      v-model="schemaDialogVisible"
      :title="`Input Schema: ${selectedTool?.namespace_name || selectedTool?.name}`"
      width="680px"
    >
      <div class="schema-modal-content">
        <div class="tab-header">
          <button
            type="button"
            :class="['tab-btn', { 'is-active': schemaTab === 'tree' }]"
            @click="schemaTab = 'tree'"
          >
            结构化契约
          </button>
          <button
            type="button"
            :class="['tab-btn', { 'is-active': schemaTab === 'raw' }]"
            @click="schemaTab = 'raw'"
          >
            原始 JSON
          </button>
        </div>

        <div v-if="schemaTab === 'tree'" class="schema-props-list">
          <div v-if="selectedProperties.length > 0" class="props-grid">
            <div v-for="prop in selectedProperties" :key="prop.key" class="prop-card">
              <div class="prop-top">
                <span class="prop-name mono-code">{{ prop.key }}</span>
                <span class="prop-type">{{ prop.type }}</span>
                <span v-if="prop.required" class="required-badge">必填</span>
              </div>
              <div class="prop-desc type-meta text-secondary">
                {{ prop.description || '无字段说明' }}
              </div>
            </div>
          </div>
          <div v-else class="empty-hint text-secondary type-body">该工具无需入参或未声明属性字段</div>
        </div>

        <div v-else class="raw-code-box">
          <pre class="schema-code"><code>{{ JSON.stringify(selectedTool?.input_schema, null, 2) }}</code></pre>
        </div>
      </div>

      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="tonal" size="sm" @click="selectedTool && goToDebug(selectedTool)">转到在线调试台</MdButton>
          <MdButton variant="outlined" size="sm" @click="schemaDialogVisible = false">关闭</MdButton>
        </div>
      </template>
    </AdaptiveModal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { PlayCircle, RefreshCw, Search, Code2, Sliders, Terminal } from 'lucide-vue-next'
import { listTools, updateToolPolicy } from '@/api/tool'
import { listServices } from '@/api/server'
import type { RegisteredTool, RegisteredService, ToolRiskLevel } from '@/api/types'
import {
  MdTable,
  MdButton,
  MdSwitch,
  MdSelect,
  MdInput,
  MdTooltip,
  MdDropdown,
  AdaptiveModal,
  type SelectOption,
  type MdTableColumn,
  type DropdownItem,
} from '@/components/m3'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const toast = useToast()

const columns: MdTableColumn<RegisteredTool>[] = [
  { key: 'name', title: '工具名称', width: '160px' },
  { key: 'namespace_name', title: '命名空间全称', width: '200px' },
  { key: 'service_id', title: '所属服务', width: '120px' },
  { key: 'description', title: '业务说明', width: '240px' },
  { key: 'risk_level', title: '风险等级', width: '90px', align: 'center' },
  { key: 'requires_confirmation', title: '人工确认', width: '90px', align: 'center' },
  { key: 'actions', title: '操作', width: '130px', align: 'right' },
]

const riskOptions: SelectOption[] = [
  { label: '全部等级', value: '' },
  { label: 'L0 (安全只读)', value: 'L0' },
  { label: 'L1 (有限写入)', value: 'L1' },
  { label: 'L2 (敏感操作)', value: 'L2' },
  { label: 'L3 (高危操作)', value: 'L3' },
]

const policyRiskOptions: SelectOption[] = [
  { label: 'L0 (安全只读、无副作用)', value: 'L0' },
  { label: 'L1 (有限写入、可撤销)', value: 'L1' },
  { label: 'L2 (敏感操作、业务副作用)', value: 'L2' },
  { label: 'L3 (高危系统级操作、破坏性)', value: 'L3' },
]

const loading = ref(false)
const tools = ref<RegisteredTool[]>([])
const services = ref<RegisteredService[]>([])

const serviceOptions = computed<SelectOption[]>(() => [
  { label: '全部服务', value: '' },
  ...services.value.map((s) => ({
    label: `${s.name} (${s.id})`,
    value: s.id,
  })),
])

function getToolRowKey(tool: RegisteredTool): string {
  return tool.id || `${tool.service_id}__${tool.name}`
}

// 策略配置状态
const policyDialogVisible = ref(false)
const savingPolicy = ref(false)
const policyTool = ref<RegisteredTool | null>(null)
const policyForm = reactive({
  risk_level: 'L0' as ToolRiskLevel,
  requires_confirmation: false,
})

function handleOpenPolicy(row: RegisteredTool) {
  policyTool.value = row
  policyForm.risk_level = row.risk_level
  policyForm.requires_confirmation = row.requires_confirmation
  policyDialogVisible.value = true
}

async function handleSavePolicy() {
  if (!policyTool.value) return
  savingPolicy.value = true
  try {
    const toolId = policyTool.value.id || `${policyTool.value.service_id}__${policyTool.value.name}`
    await updateToolPolicy(toolId, {
      risk_level: policyForm.risk_level,
      requires_confirmation: policyForm.requires_confirmation,
    })
    toast.success(`工具 "${policyTool.value.name}" 治理策略已成功更新`)
    policyDialogVisible.value = false
    await fetchTools()
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`修改策略失败: ${error.message || '未知异常'}`)
  } finally {
    savingPolicy.value = false
  }
}

const filters = reactive({
  service_id: '',
  risk_level: '',
  keyword: '',
})

const schemaDialogVisible = ref(false)
const schemaTab = ref<'tree' | 'raw'>('tree')
const selectedTool = ref<RegisteredTool | null>(null)

interface SchemaPropertyItem {
  key: string
  type: string
  description?: string
  required: boolean
}

const selectedProperties = computed<SchemaPropertyItem[]>(() => {
  if (!selectedTool.value?.input_schema) return []
  const schema = selectedTool.value.input_schema as {
    properties?: Record<string, { type?: string; description?: string }>
    required?: string[]
  }
  const props = schema.properties || {}
  const requiredList: string[] = schema.required || []

  return Object.keys(props).map((key) => ({
    key,
    type: props[key].type || 'any',
    description: props[key].description,
    required: requiredList.includes(key),
  }))
})

const filteredTools = computed(() => {
  return tools.value.filter((t) => {
    const matchService = !filters.service_id || t.service_id === filters.service_id
    const matchRisk = !filters.risk_level || t.risk_level === filters.risk_level
    const kw = filters.keyword.trim().toLowerCase()
    const matchKw =
      !kw ||
      t.name.toLowerCase().includes(kw) ||
      (t.description && t.description.toLowerCase().includes(kw))
    return matchService && matchRisk && matchKw
  })
})

async function fetchTools() {
  loading.value = true
  try {
    tools.value = await listTools(filters.service_id || undefined)
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`获取工具目录失败: ${error.message || '异常'}`)
  } finally {
    loading.value = false
  }
}

async function fetchServices() {
  try {
    services.value = await listServices(undefined, { silent: true })
  } catch {
    // ignore
  }
}

function viewSchema(tool: RegisteredTool) {
  selectedTool.value = tool
  schemaTab.value = 'tree'
  schemaDialogVisible.value = true
}

function goToDebug(tool: RegisteredTool) {
  schemaDialogVisible.value = false
  router.push({
    path: '/tools/debug',
    query: {
      service_id: tool.service_id,
      tool_name: tool.name,
    },
  })
}

function getToolActions(row: RegisteredTool): DropdownItem[] {
  return [
    {
      label: '查看 Schema',
      icon: Code2,
      onClick: () => viewSchema(row),
    },
    {
      label: '治理策略配置',
      icon: Sliders,
      onClick: () => handleOpenPolicy(row),
    },
  ]
}

onMounted(() => {
  fetchServices()
  fetchTools()
})
</script>

<style scoped>
.tool-list-page {
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

.chip-inactive {
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-outline);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.chip-warning {
  background-color: color-mix(in srgb, #f59e0b 12%, var(--md-sys-color-surface));
  color: #b45309;
  border: 1px solid color-mix(in srgb, #f59e0b 25%, transparent);
}

.risk-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--md-sys-shape-corner-small, 6px);
  font-size: 11px;
  font-weight: 700;
}

.risk-l0 {
  background-color: color-mix(in srgb, #198754 12%, var(--md-sys-color-surface));
  color: #198754;
  border: 1px solid color-mix(in srgb, #198754 25%, transparent);
}

.risk-l1 {
  background-color: color-mix(in srgb, #f59e0b 12%, var(--md-sys-color-surface));
  color: #b45309;
  border: 1px solid color-mix(in srgb, #f59e0b 25%, transparent);
}

.risk-l2 {
  background-color: color-mix(in srgb, #ea580c 14%, var(--md-sys-color-surface));
  color: #c2410c;
  border: 1px solid color-mix(in srgb, #ea580c 25%, transparent);
}

.risk-l3 {
  background-color: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.table-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  white-space: nowrap;
}

/* Modal Styling */
.m3-modal-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 12px 0;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-row.flex-row {
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  background-color: var(--md-sys-color-surface-container);
  border-radius: var(--md-sys-shape-corner-medium, 14px);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.switch-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.modal-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* Schema Modal */
.schema-modal-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tab-header {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  padding-bottom: 8px;
}

.tab-btn {
  padding: 6px 14px;
  border-radius: var(--md-sys-shape-corner-full, 9999px);
  font-size: 13px;
  font-weight: 500;
  color: var(--md-sys-color-on-surface-variant);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--md-sys-motion-duration-short2) var(--md-easing-emphasized);
}

.tab-btn.is-active {
  background-color: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
  font-weight: 600;
}

.props-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 400px;
  overflow-y: auto;
}

.prop-card {
  padding: 12px 16px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  background-color: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.prop-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.prop-type {
  font-size: 12px;
  color: var(--md-sys-color-primary);
  font-weight: 600;
}

.required-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background-color: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
  font-weight: 700;
}

.schema-code {
  background-color: var(--md-sys-color-surface-container-highest);
  color: var(--md-sys-color-on-surface);
  padding: 16px;
  border-radius: var(--md-sys-shape-corner-medium, 14px);
  border: 1px solid var(--md-sys-color-outline-variant);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  max-height: 400px;
  overflow: auto;
}

.empty-hint {
  text-align: center;
  padding: 32px 0;
}
</style>
