<template>
  <div class="server-detail-page">
    <!-- 顶部导航与操作栏 -->
    <div class="page-header">
      <div class="header-left">
        <button
          type="button"
          class="back-btn md-state-layer"
          title="返回服务列表"
          @click="$router.push('/servers/list')"
        >
          <ArrowLeft :size="20" />
        </button>
        <div>
          <h1 class="type-title-lg">服务详情: {{ server?.name || serviceId }}</h1>
          <p class="type-body-sm text-secondary">查看 MCP Server 节点契约、元数据及已持久化的可用工具</p>
        </div>
      </div>

      <div class="header-actions" v-if="server">
        <MdButton
          variant="tonal"
          @click="openEditModal"
        >
          <Pencil :size="16" />
          <span>编辑元数据</span>
        </MdButton>

        <MdButton
          variant="tonal"
          :disabled="refreshing"
          @click="handleRefresh"
        >
          <RefreshCw :size="16" :class="{ 'is-spinning': refreshing }" />
          <span>刷新工具</span>
        </MdButton>

        <MdButton
          variant="tonal"
          :class="server.status === 'active' ? 'btn-danger' : 'btn-success'"
          @click="handleToggleStatus"
        >
          <Power :size="16" />
          <span>{{ server.status === 'active' ? '停用服务' : '启用服务' }}</span>
        </MdButton>
      </div>
    </div>

    <!-- 1. 服务核心属性卡片 -->
    <MdCard variant="elevated" class="meta-card" v-loading="loading">
      <div class="card-title-row">
        <div class="title-with-icon">
          <Server :size="20" class="text-primary" />
          <h2 class="type-title-md">元数据与运行状态</h2>
        </div>
        <span
          :class="[
            'chip-pill',
            server?.status === 'active' ? 'chip-active' : server?.status === 'inactive' ? 'chip-inactive' : 'chip-degraded'
          ]"
        >
          {{ server?.status }}
        </span>
      </div>

      <div class="meta-grid" v-if="server">
        <!-- 1. Server ID (轻量单行等宽微胶囊底色) -->
        <div class="meta-field">
          <span class="field-label type-meta text-secondary">Server ID</span>
          <div class="field-value">
            <span class="tech-pill mono-code">{{ server.id }}</span>
          </div>
        </div>

        <!-- 2. 服务名称 -->
        <div class="meta-field">
          <span class="field-label type-meta text-secondary">服务名称</span>
          <span class="field-value type-body font-medium">{{ server.name }}</span>
        </div>

        <!-- 3. 服务版本 -->
        <div class="meta-field">
          <span class="field-label type-meta text-secondary">服务版本</span>
          <span class="field-value type-body">{{ server.version || '0.0.0' }}</span>
        </div>

        <!-- 4. MCP Endpoint (跨全行，技术标识微胶囊底色) -->
        <div class="meta-field full-row">
          <span class="field-label type-meta text-secondary">MCP Endpoint (Streamable HTTP)</span>
          <div class="field-value">
            <span class="tech-pill mono-code">{{ server.endpoint_url }}</span>
          </div>
        </div>

        <!-- 5. 维护人员 / 团队 -->
        <div class="meta-field">
          <span class="field-label type-meta text-secondary">维护人员 / 团队</span>
          <span class="field-value type-body">{{ server.owner || '未指定' }}</span>
        </div>

        <!-- 6. 注册时间 -->
        <div class="meta-field">
          <span class="field-label type-meta text-secondary">注册时间</span>
          <span class="field-value type-body text-secondary">{{ formatTime(server.created_at) }}</span>
        </div>

        <!-- 7. 最后更新时间 -->
        <div class="meta-field">
          <span class="field-label type-meta text-secondary">最后更新时间</span>
          <span class="field-value type-body text-secondary">{{ formatTime(server.updated_at) }}</span>
        </div>

        <!-- 8. 门户分类与认证标签 -->
        <div class="meta-field">
          <span class="field-label type-meta text-secondary">门户业务分类</span>
          <span class="field-value type-body font-medium">{{ server.category || '通用' }}</span>
        </div>

        <div class="meta-field">
          <span class="field-label type-meta text-secondary">统一认证标签</span>
          <span class="field-value type-body font-medium">{{ server.auth_label || 'Hub 统一认证' }}</span>
        </div>

        <!-- 9. 统一认证引导说明 -->
        <div class="meta-field full-row">
          <span class="field-label type-meta text-secondary">统一认证说明</span>
          <p class="field-value type-body">{{ server.auth_guide || '调用具体业务能力时，由 Capability Hub 统一进行身份校验与权限换发' }}</p>
        </div>

        <!-- 10. 认证入口地址 (若有) -->
        <div class="meta-field full-row" v-if="server.auth_entry_url">
          <span class="field-label type-meta text-secondary">统一认证/授权配置入口</span>
          <div class="field-value">
            <a :href="server.auth_entry_url" target="_blank" class="text-primary hover:underline">{{ server.auth_entry_url }}</a>
          </div>
        </div>

        <!-- 11. 适用场景与示例问法 (若有) -->
        <div class="meta-field full-row" v-if="server.usage_examples && server.usage_examples.length">
          <span class="field-label type-meta text-secondary">适用场景与示例问法</span>
          <ul class="list-disc pl-5 type-body text-secondary">
            <li v-for="(ex, idx) in server.usage_examples" :key="idx">{{ ex }}</li>
          </ul>
        </div>

        <!-- 12. 业务能力描述 (跨全行) -->
        <div class="meta-field full-row">
          <span class="field-label type-meta text-secondary">业务能力描述</span>
          <p class="field-value type-body desc-text">{{ server.description || '暂无业务描述' }}</p>
        </div>

        <!-- 13. 个人凭据接收方独立信任确认 (跨全行) -->
        <div v-if="server.credential_schema?.enabled" class="meta-field full-row">
          <span class="field-label type-meta text-secondary">个人业务凭据接收可信状态（管理员独立确认）</span>
          <div class="field-value" style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
            <span
              :class="[
                'chip-pill',
                isTrustBindingValid ? 'chip-active' : 'chip-warning'
              ]"
            >
              {{
                isTrustBindingValid
                  ? `已确认可信（绑定 v${server.trusted_credential_version} · ${server.trusted_credential_endpoint_url}）`
                  : (server.trusted_credential_recipient
                      ? '版本或目标地址已变更，须重新确认'
                      : '未确认可信（默认拒发个人凭据）')
              }}
            </span>
            <MdButton
              variant="tonal"
              size="sm"
              :disabled="updatingTrust"
              @click="handleToggleTrust(!isTrustBindingValid)"
            >
              <span>{{ isTrustBindingValid ? '撤销可信确认' : '确认接收个人凭据' }}</span>
            </MdButton>
          </div>
        </div>
      </div>
    </MdCard>

    <!-- 2. 已发现能力工具列表 (单一完整卡片 MdTable) -->
    <MdTable
      :columns="toolColumns"
      :data="tools"
      :loading="loadingTools"
      row-key="id"
      empty-text="暂未发现任何能力工具"
      empty-description="请点击右上角「刷新契约」按钮重新从 MCP 端点探测工具契约"
    >
      <template #toolbar>
        <div class="title-with-icon">
          <Wrench :size="18" class="text-secondary" />
          <span class="type-title-md font-semibold text-on-surface">已发现能力工具 ({{ tools.length }})</span>
        </div>
        <span class="type-meta text-secondary">
          工具通过 MCP tools/list 协议提取并持久化
        </span>
      </template>

      <!-- 列插槽：工具名称 -->
      <template #cell-name="{ row }">
        <span class="mono-code truncate max-w-[160px] block">{{ row.name }}</span>
      </template>

      <!-- 列插槽：命名空间全称 -->
      <template #cell-namespace_name="{ row }">
        <span class="mono-code truncate max-w-[220px] block">{{ row.namespace_name || `${row.service_id}__${row.name}` }}</span>
      </template>

      <!-- 列插槽：描述 (单行截断 + Tooltip) -->
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

      <!-- 列插槽：操作 -->
      <template #cell-actions="{ row }">
        <div class="action-buttons">
          <MdButton variant="text" size="sm" @click="viewSchema(row)">
            <Code2 :size="14" />
            <span>Schema</span>
          </MdButton>
          <MdButton variant="text" size="sm" @click="goToDebug(row)">
            <Terminal :size="14" />
            <span>调试</span>
          </MdButton>
        </div>
      </template>
    </MdTable>

    <!-- 3. JSON Schema 模态框 (AdaptiveModal) -->
    <AdaptiveModal
      v-model="schemaDialogVisible"
      :title="`Input Schema: ${selectedTool?.name}`"
      width="640px"
    >
      <div class="schema-box">
        <pre class="schema-code"><code>{{ JSON.stringify(selectedTool?.input_schema, null, 2) }}</code></pre>
      </div>
      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="tonal" @click="selectedTool && goToDebug(selectedTool)">前往调试</MdButton>
          <MdButton variant="outlined" @click="schemaDialogVisible = false">关闭</MdButton>
        </div>
      </template>
    </AdaptiveModal>

    <!-- 4. 编辑服务与门户元数据模态框 -->
    <AdaptiveModal
      v-model="editModalVisible"
      title="编辑服务与门户展示元数据"
      width="680px"
    >
      <div class="edit-form-wrapper">
        <div class="form-row">
          <label class="form-label">服务友好名称 *</label>
          <input v-model="editForm.name" type="text" class="custom-input" placeholder="输入易于业务理解的服务显示名" />
        </div>
        <div class="form-row-grid">
          <div class="form-row">
            <label class="form-label">业务分类标签</label>
            <input v-model="editForm.category" type="text" class="custom-input" placeholder="例如: 业务协作 / 知识检索 / 数据分析" />
          </div>
          <div class="form-row">
            <label class="form-label">维护人 / 团队</label>
            <input v-model="editForm.owner" type="text" class="custom-input" placeholder="责任团队或联系人" />
          </div>
        </div>
        <div class="form-row-grid">
          <div class="form-row">
            <label class="form-label">统一认证方式标签</label>
            <input v-model="editForm.auth_label" type="text" class="custom-input" placeholder="例如: Hub 统一认证 / 免登录 / 团队Token" />
          </div>
          <div class="form-row">
            <label class="form-label">统一认证入口 URL (可选)</label>
            <input v-model="editForm.auth_entry_url" type="text" class="custom-input" placeholder="https://..." />
          </div>
        </div>
        <div class="form-row">
          <label class="form-label">统一认证说明引导</label>
          <input v-model="editForm.auth_guide" type="text" class="custom-input" placeholder="首次调用能力时的认证指引文案" />
        </div>
        <div class="form-row">
          <label class="form-label">业务能力描述</label>
          <textarea v-model="editForm.description" rows="3" class="custom-textarea" placeholder="面向非开发者的通俗业务功能介绍"></textarea>
        </div>
        <div class="form-row">
          <label class="form-label">适用场景与示例提问（每行一条）</label>
          <textarea v-model="editForm.examples_text" rows="3" class="custom-textarea" placeholder="帮我查询上周各渠道消息发送总量&#10;分析当前投资组合表现"></textarea>
        </div>
      </div>
      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="text" @click="editModalVisible = false">取消</MdButton>
          <MdButton variant="tonal" :disabled="savingEdit" @click="handleSaveMetadata">
            <span>{{ savingEdit ? '保存中...' : '保存修改' }}</span>
          </MdButton>
        </div>
      </template>
    </AdaptiveModal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, RefreshCw, Power, Server, Wrench, Code2, Terminal, Pencil } from 'lucide-vue-next'
import { getService, updateServiceStatus, updateServiceCredentialTrust, refreshServiceTools, updateServiceMetadata } from '@/api/server'
import { listTools } from '@/api/tool'
import type { RegisteredService, RegisteredTool, ServiceStatus } from '@/api/types'
import { MdCard, MdButton, MdTable, MdTooltip, AdaptiveModal, type MdTableColumn } from '@/components/m3'
import { useToast } from '@/composables/useToast'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const serviceId = route.params.id as string

const toolColumns: MdTableColumn<RegisteredTool>[] = [
  { key: 'name', title: '工具名称', width: '150px' },
  { key: 'namespace_name', title: '命名空间全称', width: '200px' },
  { key: 'description', title: '描述', width: '260px' },
  { key: 'risk_level', title: '风险等级', width: '90px', align: 'center' },
  { key: 'requires_confirmation', title: '人工确认', width: '90px', align: 'center' },
  { key: 'actions', title: '操作', width: '130px', align: 'right' },
]

const loading = ref(false)
const loadingTools = ref(false)
const refreshing = ref(false)
const updatingTrust = ref(false)
const server = ref<RegisteredService | null>(null)
const tools = ref<RegisteredTool[]>([])

const isTrustBindingValid = computed(() => {
  if (!server.value) return false
  return Boolean(
    server.value.trusted_credential_recipient &&
      server.value.trusted_credential_version === server.value.version &&
      server.value.trusted_credential_endpoint_url === server.value.endpoint_url
  )
})

async function handleToggleTrust(trusted: boolean) {
  if (!server.value) return
  updatingTrust.value = true
  try {
    server.value = await updateServiceCredentialTrust(serviceId, trusted)
    toast.success(trusted ? '已确认该服务为可信个人凭据接收方' : '已撤销该服务的凭据接收信任')
  } catch (err: unknown) {
    const error = err as { response?: { data?: { detail?: string } }; message?: string }
    toast.error(`操作失败: ${error.response?.data?.detail || error.message || '未知错误'}`)
  } finally {
    updatingTrust.value = false
  }
}

const schemaDialogVisible = ref(false)
const selectedTool = ref<RegisteredTool | null>(null)

// 编辑模态框状态与表单
const editModalVisible = ref(false)
const savingEdit = ref(false)
const editForm = reactive({
  name: '',
  description: '',
  owner: '',
  category: '',
  auth_mode: 'platform_sso',
  auth_label: 'Hub 统一认证',
  auth_guide: '',
  auth_entry_url: '',
  examples_text: '',
})

function openEditModal() {
  if (!server.value) return
  editForm.name = server.value.name || ''
  editForm.description = server.value.description || ''
  editForm.owner = server.value.owner || ''
  editForm.category = server.value.category || '通用'
  editForm.auth_mode = server.value.auth_mode || 'platform_sso'
  editForm.auth_label = server.value.auth_label || 'Hub 统一认证'
  editForm.auth_guide = server.value.auth_guide || ''
  editForm.auth_entry_url = server.value.auth_entry_url || ''
  editForm.examples_text = (server.value.usage_examples || []).join('\n')
  editModalVisible.value = true
}

async function handleSaveMetadata() {
  if (!editForm.name.trim()) {
    toast.warning('服务名称不能为空')
    return
  }
  savingEdit.value = true
  try {
    const examples = editForm.examples_text
      .split('\n')
      .map(s => s.trim())
      .filter(Boolean)
    const updated = await updateServiceMetadata(serviceId, {
      name: editForm.name.trim(),
      description: editForm.description.trim(),
      owner: editForm.owner.trim(),
      category: editForm.category.trim() || '通用',
      auth_mode: editForm.auth_mode.trim(),
      auth_label: editForm.auth_label.trim() || 'Hub 统一认证',
      auth_guide: editForm.auth_guide.trim(),
      auth_entry_url: editForm.auth_entry_url.trim(),
      usage_examples: examples,
    })
    server.value = updated
    toast.success('元数据更新成功')
    editModalVisible.value = false
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`更新失败: ${error.message || '未知错误'}`)
  } finally {
    savingEdit.value = false
  }
}

function formatTime(isoStr?: string) {
  if (!isoStr) return '-'
  try {
    return new Date(isoStr).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return isoStr
  }
}

async function fetchDetail() {
  loading.value = true
  try {
    server.value = await getService(serviceId)
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`获取服务详情失败: ${error.message || '网络异常'}`)
  } finally {
    loading.value = false
  }
}

async function fetchTools() {
  loadingTools.value = true
  try {
    tools.value = await listTools(serviceId)
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`获取工具列表失败: ${error.message || '异常'}`)
  } finally {
    loadingTools.value = false
  }
}

async function handleRefresh() {
  refreshing.value = true
  try {
    const res = await refreshServiceTools(serviceId)
    toast.success(`刷新成功，已重新发现 ${res.tools_discovered} 个工具契约`)
    await Promise.all([fetchDetail(), fetchTools()])
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`刷新失败: ${error.message || '错误'}`)
  } finally {
    refreshing.value = false
  }
}

async function handleToggleStatus() {
  if (!server.value) return
  const isActivating = server.value.status !== 'active'
  const actionText = isActivating ? '启用' : '停用'
  const targetStatus: ServiceStatus = isActivating ? 'active' : 'inactive'

  if (confirm(`确定要${actionText}服务 "${server.value.name}" 吗？`)) {
    try {
      server.value = await updateServiceStatus(serviceId, targetStatus)
      toast.success(`已${actionText}服务`)
    } catch (err: unknown) {
      const error = err as { message?: string }
      toast.error(`更新状态失败: ${error.message || '错误'}`)
    }
  }
}

function viewSchema(tool: RegisteredTool) {
  selectedTool.value = tool
  schemaDialogVisible.value = true
}

function goToDebug(tool: RegisteredTool) {
  router.push({
    path: '/tools/debug',
    query: {
      service_id: tool.service_id,
      tool_name: tool.name,
    },
  })
}

onMounted(() => {
  fetchDetail()
  fetchTools()
})
</script>

<style scoped>
.server-detail-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--md-sys-shape-corner-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--md-sys-color-on-surface-variant);
  background: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
  transition: color var(--md-sys-motion-duration-short2) var(--md-sys-motion-easing-standard);
}

.back-btn:hover {
  color: var(--md-sys-color-on-surface);
  background: var(--md-sys-color-surface-container-high);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.text-secondary {
  color: var(--md-sys-color-on-surface-variant);
}

.text-primary {
  color: var(--md-sys-color-primary);
}

.is-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.meta-card,
.tools-card {
  padding: 24px;
  border-radius: var(--md-sys-shape-corner-medium, 16px);
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chip-pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--md-sys-shape-corner-full, 9999px);
  font-size: 12px;
  font-weight: 500;
  line-height: 16px;
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

.chip-warning {
  background-color: color-mix(in srgb, #f59e0b 12%, var(--md-sys-color-surface));
  color: #b45309;
  border: 1px solid color-mix(in srgb, #f59e0b 25%, transparent);
}

/* 3 列扁平键值网格 (AI Studio 极简控制台美学) */
.meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  column-gap: 32px;
  row-gap: 20px;
}

@media (max-width: 768px) {
  .meta-grid {
    grid-template-columns: 1fr;
    row-gap: 16px;
  }
}

.meta-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.meta-field.full-row {
  grid-column: 1 / -1;
}

.field-label {
  font-size: 12px;
  line-height: 16px;
  color: var(--md-sys-color-on-surface-variant);
  font-weight: 500;
  user-select: none;
}

.field-value {
  color: var(--md-sys-color-on-surface);
}

.type-body {
  font-size: 14px;
  line-height: 20px;
}

.font-medium {
  font-weight: 500;
}

/* 单行等宽微胶囊底色 (Server ID 与 MCP Endpoint 等技术标识) */
.tech-pill {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 3px 10px;
  border-radius: var(--md-sys-shape-corner-small, 6px);
  background-color: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  color: var(--md-sys-color-on-surface);
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 13px;
  line-height: 18px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.desc-text {
  color: var(--md-sys-color-on-surface);
  line-height: 1.6;
  margin: 0;
}

.risk-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--md-sys-shape-corner-small, 6px);
  font-size: 11px;
  font-weight: 700;
}

.risk-l0 {
  background-color: #d1e7dd;
  color: #0f5132;
}

.risk-l1 {
  background-color: #fff3cd;
  color: #664d03;
}

.risk-l2 {
  background-color: #ffe5d0;
  color: #a83800;
}

.risk-l3 {
  background-color: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 4px;
}

.btn-danger {
  background-color: var(--md-sys-color-error) !important;
  color: var(--md-sys-color-on-error) !important;
}

.btn-success {
  background-color: #198754 !important;
  color: #ffffff !important;
}

.schema-box {
  padding: 8px 0;
}

.schema-code {
  background-color: var(--md-sys-color-surface-container-highest);
  color: var(--md-sys-color-on-surface);
  padding: 16px;
  border-radius: var(--md-sys-shape-corner-medium, 14px);
  border: 1px solid var(--md-sys-color-outline-variant);
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 13px;
  line-height: 1.45;
  max-height: 450px;
  overflow: auto;
}

.modal-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.edit-form-wrapper {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 8px 0;
}

.form-row-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--md-sys-color-on-surface);
}

.custom-input,
.custom-textarea {
  width: 100%;
  padding: 10px 14px;
  border-radius: var(--md-sys-shape-corner-medium, 10px);
  border: 1px solid var(--md-sys-color-outline-variant);
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s ease;
}

.custom-input:focus,
.custom-textarea:focus {
  border-color: var(--md-sys-color-primary);
}
</style>
