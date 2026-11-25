<template>
  <div class="server-list-page">
    <!-- 页头区域 -->
    <div class="page-header">
      <div class="title-area">
        <h1 class="type-title-lg">MCP 服务管理</h1>
        <p class="type-body text-secondary">管理并发现平台接入的各 MCP Server 实例与 Streamable HTTP 协议端点</p>
      </div>
      <div class="header-action-group">
        <MdButton variant="tonal" @click="$router.push('/admin/servers/publish')">
          <UploadCloud :size="18" />
          <span>自助发布插件</span>
        </MdButton>
        <MdButton variant="outlined" @click="$router.push('/servers/register')">
          <Plus :size="18" />
          <span>手动接入服务</span>
        </MdButton>
      </div>
    </div>

    <!-- 紧凑单行筛选工具栏 (36px 等高内联) -->
    <div class="filter-toolbar">
      <div class="filter-controls">
        <MdSelect
          v-model="filters.status"
          :options="statusOptions"
          prefix="服务状态："
          placeholder="全部状态"
          size="sm"
          style="min-width: 170px"
        />

        <MdInput
          v-model="filters.keyword"
          placeholder="按服务标识、名称、维护人过滤"
          size="sm"
          clearable
          style="width: 250px"
        >
          <template #prefix>
            <Search :size="15" class="text-secondary" />
          </template>
        </MdInput>
      </div>

      <div class="filter-actions">
        <span class="count-tag type-meta text-secondary">
          共 <strong class="text-on-surface">{{ filteredServers.length }}</strong> 个服务实例
        </span>
        <MdButton variant="tonal" size="sm" :disabled="loading" @click="fetchServers">
          <RefreshCw :size="15" :class="{ 'is-spinning': loading }" />
          <span>刷新</span>
        </MdButton>
      </div>
    </div>

    <!-- 骨架屏加载态 (卡片网格) -->
    <div v-if="loading" class="server-grid">
      <div v-for="i in 6" :key="`skeleton-${i}`" class="server-card skeleton-card">
        <div class="card-head">
          <div class="skeleton-icon" />
          <div class="skeleton-head-info">
            <div class="skeleton-bar title-bar" />
            <div class="skeleton-bar id-bar" />
          </div>
        </div>
        <div class="card-body">
          <div class="skeleton-bar desc-bar-1" />
          <div class="skeleton-bar desc-bar-2" />
          <div class="skeleton-spec-box" />
        </div>
        <div class="card-footer">
          <div class="skeleton-bar btn-bar" />
          <div class="skeleton-bar actions-bar" />
        </div>
      </div>
    </div>

    <!-- 真实数据：卡片式网格展示 -->
    <div v-else-if="filteredServers.length > 0" class="server-grid">
      <div
        v-for="server in filteredServers"
        :key="server.id"
        class="server-card md-state-layer"
      >
        <!-- 卡片头部：图标 + 服务名称 + 状态药丸 + 更多菜单 -->
        <div class="card-head">
          <div class="server-icon-wrap">
            <Server :size="18" />
          </div>
          <div class="head-info">
            <div class="name-status-row">
              <h3 class="server-title truncate" :title="server.name">{{ server.name }}</h3>
              <span :class="['chip-pill', getStatusChipClass(server.status)]">
                {{ server.status }}
              </span>
            </div>
            <div class="id-row">
              <span class="mono-code">{{ server.id }}</span>
              <span v-if="server.version" class="version-tag type-meta text-secondary">v{{ server.version }}</span>
            </div>
          </div>
          <MdDropdown :items="getMoreActions(server)" placement="bottom-end" />
        </div>

        <!-- 卡片主体：描述与技术规格 -->
        <div class="card-body">
          <p class="server-desc type-body text-secondary" :title="server.description || ''">
            {{ server.description || '暂无业务描述说明' }}
          </p>

          <div class="meta-specs">
            <!-- MCP Endpoint -->
            <div class="spec-row">
              <span class="spec-label type-meta text-secondary">MCP Endpoint</span>
              <MdTooltip :content="server.endpoint_url" placement="top">
                <span class="spec-val mono-code truncate cursor-help">{{ server.endpoint_url }}</span>
              </MdTooltip>
            </div>

            <!-- 维护人与更新时间分列 -->
            <div class="spec-inline-grid">
              <div class="spec-col">
                <span class="spec-label type-meta text-secondary">维护人员</span>
                <span class="spec-val type-meta font-medium truncate">{{ server.owner || '未指派' }}</span>
              </div>
              <div class="spec-col">
                <span class="spec-label type-meta text-secondary">最近更新</span>
                <span class="spec-val type-meta tabular-nums text-secondary truncate">{{ formatTime(server.updated_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 卡片底栏：详情主入口 + 快捷状态切换/测连 -->
        <div class="card-footer">
          <MdButton
            variant="tonal"
            size="sm"
            class="btn-detail"
            @click="$router.push(`/servers/${server.id}`)"
          >
            <span>服务详情</span>
            <ArrowRight :size="14" />
          </MdButton>

          <div class="footer-quick-actions">
            <MdButton
              variant="text"
              size="sm"
              :disabled="testingId === server.id"
              @click="handleTestConnection(server)"
            >
              <span v-if="testingId === server.id">测连中...</span>
              <span v-else>测连</span>
            </MdButton>

            <MdButton
              variant="text"
              size="sm"
              :class="server.status === 'active' ? 'text-error' : 'text-success'"
              @click="handleToggleStatus(server)"
            >
              {{ server.status === 'active' ? '停用' : '启用' }}
            </MdButton>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state-box">
      <div class="empty-icon-wrap">
        <Layers :size="36" class="text-secondary" />
      </div>
      <div class="empty-text">
        <h3 class="type-title-md font-semibold text-on-surface">暂无匹配的 MCP 服务</h3>
        <p class="type-body text-secondary">请尝试调整上方筛选条件，或立即注册接入新服务</p>
      </div>
      <MdButton variant="tonal" size="sm" @click="$router.push('/servers/register')">
        <Plus :size="16" />
        <span>注册 MCP 服务</span>
      </MdButton>
    </div>

    <!-- 编辑服务元数据模态框 (AdaptiveModal) -->
    <AdaptiveModal
      v-model="editDialogVisible"
      title="编辑服务元数据"
      width="520px"
    >
      <div class="m3-modal-form">
        <div class="form-row">
          <label class="type-meta text-secondary">Server ID</label>
          <div><span class="mono-code">{{ editingServer?.id }}</span></div>
        </div>

        <div class="form-row">
          <label class="type-meta" for="edit-name">服务名称 *</label>
          <MdInput
            id="edit-name"
            v-model="editForm.name"
            size="sm"
            placeholder="服务显示名称"
          />
        </div>

        <div class="form-row">
          <label class="type-meta" for="edit-owner">维护人员</label>
          <MdInput
            id="edit-owner"
            v-model="editForm.owner"
            size="sm"
            placeholder="负责人或维护团队"
          />
        </div>

        <div class="form-row">
          <label class="type-meta" for="edit-desc">业务描述</label>
          <textarea
            id="edit-desc"
            v-model="editForm.description"
            class="m3-dialog-textarea"
            rows="3"
            placeholder="简要业务能力与工具说明"
          ></textarea>
        </div>
      </div>

      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="text" size="sm" @click="editDialogVisible = false">取消</MdButton>
          <MdButton variant="tonal" size="sm" :disabled="savingEdit" @click="handleSaveEdit">
            <span v-if="!savingEdit">保存修改</span>
            <span v-else>正在保存...</span>
          </MdButton>
        </div>
      </template>
    </AdaptiveModal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, RefreshCw, Search, Edit2, Wifi, Server, ArrowRight, Layers, UploadCloud } from 'lucide-vue-next'
import {
  listServices,
  updateServiceStatus,
  updateServiceMetadata,
  refreshServiceTools,
  testServerConnection,
} from '@/api/server'
import type { RegisteredService, ServiceStatus } from '@/api/types'
import {
  MdButton,
  MdSelect,
  MdInput,
  MdTooltip,
  MdDropdown,
  AdaptiveModal,
  type SelectOption,
  type DropdownItem,
} from '@/components/m3'
import { useToast } from '@/composables/useToast'

const toast = useToast()

const statusOptions: SelectOption[] = [
  { label: '全部状态', value: '' },
  { label: '正常 (active)', value: 'active' },
  { label: '已停用 (inactive)', value: 'inactive' },
  { label: '已降级 (degraded)', value: 'degraded' },
  { label: '待处理 (pending)', value: 'pending' },
]

const loading = ref(false)
const servers = ref<RegisteredService[]>([])
const testingId = ref<string | null>(null)
const refreshingId = ref<string | null>(null)

// 编辑模态框状态
const editDialogVisible = ref(false)
const savingEdit = ref(false)
const editingServer = ref<RegisteredService | null>(null)
const editForm = reactive({
  name: '',
  owner: '',
  description: '',
})

function handleOpenEdit(server: RegisteredService) {
  editingServer.value = server
  editForm.name = server.name
  editForm.owner = server.owner || ''
  editForm.description = server.description || ''
  editDialogVisible.value = true
}

async function handleSaveEdit() {
  if (!editingServer.value) return
  if (!editForm.name.trim()) {
    toast.warning('服务名称不能为空')
    return
  }
  savingEdit.value = true
  try {
    await updateServiceMetadata(editingServer.value.id, {
      name: editForm.name.trim(),
      owner: editForm.owner.trim(),
      description: editForm.description.trim(),
    })
    toast.success('服务元数据修改成功')
    editDialogVisible.value = false
    await fetchServers()
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`修改失败: ${error.message || '未知错误'}`)
  } finally {
    savingEdit.value = false
  }
}

const filters = reactive({
  keyword: '',
  status: '',
})

const filteredServers = computed(() => {
  return servers.value.filter((s) => {
    const matchStatus = !filters.status || s.status === filters.status
    const kw = filters.keyword.trim().toLowerCase()
    const matchKw =
      !kw ||
      s.id.toLowerCase().includes(kw) ||
      s.name.toLowerCase().includes(kw) ||
      (s.owner && s.owner.toLowerCase().includes(kw))
    return matchStatus && matchKw
  })
})

function getStatusChipClass(status: string): string {
  if (status === 'active') return 'chip-active'
  if (status === 'inactive') return 'chip-inactive'
  return 'chip-degraded'
}

function formatTime(isoStr?: string) {
  if (!isoStr) return '-'
  try {
    return new Date(isoStr).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return isoStr
  }
}

async function fetchServers() {
  loading.value = true
  try {
    servers.value = await listServices(undefined, { silent: true })
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`获取服务列表失败: ${error.message || '网络异常'}`)
  } finally {
    loading.value = false
  }
}

async function handleTestConnection(server: RegisteredService) {
  testingId.value = server.id
  try {
    const res = await testServerConnection(server.id)
    if (res.success) {
      toast.success(`连接正常: ${server.name} (${server.endpoint_url})`)
    } else {
      toast.warning(`连接检查反馈: ${res.message || '响应异常'}`)
    }
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`服务连接测试失败: ${error.message || '网络错误'}`)
  } finally {
    testingId.value = null
  }
}

async function handleRefreshTools(server: RegisteredService) {
  refreshingId.value = server.id
  try {
    const res = await refreshServiceTools(server.id)
    toast.success(`刷新成功，已重新发现 ${res.tools_discovered} 个工具契约`)
    await fetchServers()
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`刷新工具失败: ${error.message || '异常'}`)
  } finally {
    refreshingId.value = null
  }
}

async function handleToggleStatus(server: RegisteredService) {
  const isActivating = server.status !== 'active'
  const actionText = isActivating ? '启用' : '停用'
  const targetStatus: ServiceStatus = isActivating ? 'active' : 'inactive'

  if (confirm(`确定要${actionText}服务 "${server.name}" (${server.id}) 吗？`)) {
    try {
      await updateServiceStatus(server.id, targetStatus)
      toast.success(`已${actionText}服务: ${server.name}`)
      await fetchServers()
    } catch (err: unknown) {
      const error = err as { message?: string }
      toast.error(`操作失败: ${error.message || '错误'}`)
    }
  }
}

function getMoreActions(server: RegisteredService): DropdownItem[] {
  return [
    {
      label: '编辑元数据',
      icon: Edit2,
      onClick: () => handleOpenEdit(server),
    },
    {
      label: testingId.value === server.id ? '正在测连...' : '测试连接',
      icon: Wifi,
      disabled: testingId.value === server.id,
      onClick: () => handleTestConnection(server),
    },
    {
      label: refreshingId.value === server.id ? '正在刷新...' : '刷新工具契约',
      icon: RefreshCw,
      disabled: refreshingId.value === server.id,
      onClick: () => handleRefreshTools(server),
    },
  ]
}

onMounted(() => {
  fetchServers()
})
</script>

<style scoped>
.server-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-action-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-area {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.text-secondary {
  color: var(--md-sys-color-on-surface-variant);
}

.text-on-surface {
  color: var(--md-sys-color-on-surface);
}

.text-error {
  color: var(--md-sys-color-error) !important;
}

.text-success {
  color: #198754 !important;
}

.is-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 筛选工具栏 */
.filter-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px 16px;
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-radius-card, 16px);
  box-sizing: border-box;
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
  gap: 16px;
  margin-left: auto;
}

.count-tag {
  user-select: none;
}

/* 卡片网格布局 (自适应 340px 列宽) */
.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  width: 100%;
}

/* 单个服务卡片 */
.server-card {
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-radius-card, 16px);
  padding: 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 12px;
  transition: all var(--md-sys-motion-duration-short2) var(--md-easing-emphasized);
}

.server-card:hover {
  border-color: var(--md-sys-color-outline);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
}

/* 卡片头部 */
.card-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.server-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: var(--md-sys-shape-corner-medium, 10px);
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.head-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.name-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.server-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 20px;
  color: var(--md-sys-color-on-surface);
}

.id-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-tag {
  font-size: 11px;
}

/* 卡片主体 */
.card-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}

.server-desc {
  margin: 0;
  font-size: 13px;
  line-height: 19px;
  min-height: 38px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

/* 技术规格容器 */
.meta-specs {
  background-color: var(--md-sys-color-surface-container-low);
  border-radius: var(--md-sys-shape-corner-small, 8px);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid var(--md-sys-color-outline-variant);
}

.spec-row {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.spec-inline-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.spec-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.spec-label {
  font-size: 11px;
}

.spec-val {
  font-size: 12px;
}

/* 卡片底部操作栏 */
.card-footer {
  border-top: 1px solid var(--md-sys-color-outline-variant);
  padding-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.btn-detail {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.footer-quick-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

/* 通用标签药丸 */
.mono-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  padding: 2px 6px;
  border-radius: 4px;
  display: inline-block;
  line-height: 1.4;
}

.chip-pill {
  display: inline-block;
  padding: 1px 7px;
  border-radius: var(--md-sys-shape-corner-full, 9999px);
  font-size: 11px;
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

.chip-degraded {
  background-color: color-mix(in srgb, #f59e0b 12%, var(--md-sys-color-surface));
  color: #b45309;
  border: 1px solid color-mix(in srgb, #f59e0b 25%, transparent);
}

/* 空状态 */
.empty-state-box {
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-radius-card, 16px);
  padding: 48px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  text-align: center;
}

.empty-icon-wrap {
  width: 60px;
  height: 60px;
  border-radius: var(--md-sys-shape-corner-medium, 14px);
  background-color: var(--md-sys-color-surface-container);
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* 骨架屏动画 */
.skeleton-card {
  pointer-events: none;
}

.skeleton-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background-color: var(--md-sys-color-surface-container);
  animation: pulse 1.5s infinite ease-in-out;
}

.skeleton-head-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.skeleton-bar {
  border-radius: 4px;
  background-color: var(--md-sys-color-surface-container);
  animation: pulse 1.5s infinite ease-in-out;
}

.title-bar { width: 50%; height: 16px; }
.id-bar { width: 30%; height: 12px; }
.desc-bar-1 { width: 90%; height: 12px; margin-top: 8px; }
.desc-bar-2 { width: 65%; height: 12px; margin-top: 6px; }
.skeleton-spec-box { width: 100%; height: 64px; border-radius: 8px; background-color: var(--md-sys-color-surface-container); margin-top: 10px; animation: pulse 1.5s infinite ease-in-out; }
.btn-bar { width: 80px; height: 28px; border-radius: 6px; }
.actions-bar { width: 90px; height: 28px; border-radius: 6px; }

@keyframes pulse {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}

/* Modal Form */
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

.m3-dialog-textarea {
  width: 100%;
  padding: 10px 14px;
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-small, 8px);
  color: var(--md-sys-color-on-surface);
  font-family: inherit;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
}

.m3-dialog-textarea:focus {
  border-color: var(--md-sys-color-primary);
}

.modal-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
