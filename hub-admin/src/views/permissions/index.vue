<template>
  <div class="permissions-view">
    <!-- 顶部标题与操作栏 -->
    <div class="page-header">
      <div class="title-area">
        <h1 class="type-title-lg">功能权限审批</h1>
        <p class="type-body text-secondary">
          集中审批业务用户针对敏感 MCP 工具（L1/L2 等）的开通申请；审批通过后实时写入授权库，用户本地智能客户端零配置自动点亮
        </p>
      </div>
      <div class="header-actions">
        <MdButton variant="tonal" :disabled="loading" @click="loadRequests">
          <RefreshCw :size="16" :class="{ 'is-spinning': loading }" />
          <span>刷新数据</span>
        </MdButton>
      </div>
    </div>

    <!-- 主数据表格卡片 -->
    <MdTable
      :columns="columns"
      :data="pagedRequests"
      :loading="loading"
      row-key="id"
      empty-text="暂无匹配的权限申请记录"
      empty-description="用户在能力门户申请非 L0 敏感工具功能后，申请单将在此统一流转审批"
    >
      <!-- 顶部嵌入式工具栏 -->
      <template #toolbar>
        <div class="table-toolbar-inner">
          <!-- 状态过滤 Tab 胶囊组 -->
          <div class="status-tab-group">
            <button
              v-for="tab in statusTabs"
              :key="tab.value"
              type="button"
              class="tab-pill-btn"
              :class="{ 'is-active': activeStatusFilter === tab.value }"
              @click="setStatusFilter(tab.value)"
            >
              <span>{{ tab.label }}</span>
              <span v-if="tab.count !== undefined" class="tab-count-badge">{{ tab.count }}</span>
            </button>
          </div>

          <!-- 搜索输入框 -->
          <div class="toolbar-right">
            <div class="search-input-wrapper">
              <Search :size="15" class="search-icon" />
              <input
                v-model="searchKeyword"
                type="text"
                placeholder="搜索申请人、服务或工具名..."
                class="search-input"
              />
              <button
                v-if="searchKeyword"
                type="button"
                class="clear-search-btn"
                title="清空搜索"
                @click="searchKeyword = ''"
              >
                <X :size="13" />
              </button>
            </div>
          </div>
        </div>
      </template>

      <!-- 列插槽：申请单号 -->
      <template #cell-id="{ row }">
        <span class="mono-code text-xs text-primary font-medium">{{ row.id }}</span>
      </template>

      <!-- 列插槽：申请人 -->
      <template #cell-user_name="{ row }">
        <div class="user-cell">
          <div class="user-avatar-small">
            <User :size="13" />
          </div>
          <div class="user-meta-lines">
            <span class="user-name-text font-medium text-sm">{{ row.user_name || '未填姓名' }}</span>
            <span class="user-id-sub mono text-xs text-secondary">{{ row.user_id }}</span>
          </div>
        </div>
      </template>

      <!-- 列插槽：目标服务 -->
      <template #cell-service_name="{ row }">
        <div class="service-cell">
          <span class="font-medium text-sm text-on-surface">{{ row.service_name || row.service_id }}</span>
          <span class="mono text-xs text-secondary">{{ row.service_id }}</span>
        </div>
      </template>

      <!-- 列插槽：申请功能列表 -->
      <template #cell-tool_names="{ row }">
        <div class="tools-tags-group">
          <span
            v-for="tName in row.tool_names"
            :key="tName"
            class="tool-tag mono"
            :title="tName"
          >
            {{ tName }}
          </span>
        </div>
      </template>

      <!-- 列插槽：业务用途说明 -->
      <template #cell-reason="{ row }">
        <MdTooltip v-if="row.reason" :content="row.reason" placement="top">
          <span class="reason-cell-text truncate max-w-[280px] block text-sm cursor-help">
            {{ row.reason }}
          </span>
        </MdTooltip>
        <span v-else class="text-secondary text-xs opacity-60">未填写说明</span>
      </template>

      <!-- 列插槽：审批状态 -->
      <template #cell-status="{ row }">
        <span :class="['status-chip', `status-${row.status}`]">
          <span v-if="row.status === 'approved'">🟢 审批通过</span>
          <span v-else-if="row.status === 'rejected'">🔴 已驳回</span>
          <span v-else>🟡 待审批</span>
        </span>
      </template>

      <!-- 列插槽：提交时间 -->
      <template #cell-created_at="{ row }">
        <span class="type-meta tabular-nums text-secondary text-xs">{{ formatTime(row.created_at) }}</span>
      </template>

      <!-- 列插槽：审批信息 -->
      <template #cell-reviewed_info="{ row }">
        <div v-if="row.status !== 'pending'" class="reviewed-cell">
          <div class="reviewed-by-line text-xs font-medium">
            <span>{{ row.reviewed_by || '管理员' }}</span>
            <span class="text-secondary text-[11px] ml-1">{{ formatDayOnly(row.reviewed_at) }}</span>
          </div>
          <MdTooltip v-if="row.comment" :content="row.comment" placement="top">
            <span class="reviewed-comment-text truncate max-w-[170px] text-xs text-secondary block cursor-help">
              批注: {{ row.comment }}
            </span>
          </MdTooltip>
          <span v-else class="text-secondary text-xs opacity-60">无批注</span>
        </div>
        <span v-else class="text-secondary text-xs opacity-40">-</span>
      </template>

      <!-- 列插槽：操作按钮 -->
      <template #cell-actions="{ row }">
        <div v-if="row.status === 'pending'" class="action-buttons-inline">
          <MdButton
            variant="tonal"
            size="sm"
            class="btn-inline-approve"
            @click.stop="openReviewModal(row, 'approved')"
          >
            <Check :size="14" />
            <span>同意</span>
          </MdButton>
          <MdButton
            variant="outlined"
            size="sm"
            class="btn-inline-reject"
            @click.stop="openReviewModal(row, 'rejected')"
          >
            <X :size="14" />
            <span>驳回</span>
          </MdButton>
        </div>
        <div v-else class="action-done-label">
          <span class="text-xs text-secondary opacity-60">已办结</span>
        </div>
      </template>

      <!-- 分页底栏插槽 -->
      <template #pagination>
        <MdPagination
          v-model:page="page"
          v-model:page-size="pageSize"
          :total="totalCount"
          :page-size-options="[10, 20, 50, 100]"
        />
      </template>
    </MdTable>

    <!-- 审批处理弹窗 -->
    <AdaptiveModal
      v-model="reviewModalVisible"
      :title="currentReviewAction === 'approved' ? '同意功能开通申请' : '驳回功能申请'"
      width="520px"
    >
      <div v-if="selectedRequest" class="review-modal-body">
        <div class="modal-summary-card">
          <div class="summary-line">
            <span class="text-secondary text-xs">申请人员:</span>
            <span class="font-medium text-sm">{{ selectedRequest.user_name || '未填' }} ({{ selectedRequest.user_id }})</span>
          </div>
          <div class="summary-line mt-1">
            <span class="text-secondary text-xs">目标服务:</span>
            <span class="font-medium text-sm">{{ selectedRequest.service_name || selectedRequest.service_id }}</span>
          </div>
          <div class="summary-line mt-1">
            <span class="text-secondary text-xs">开通功能:</span>
            <div class="tools-tags-group">
              <span v-for="t in selectedRequest.tool_names" :key="t" class="tool-tag mono">{{ t }}</span>
            </div>
          </div>
          <div class="summary-line mt-1">
            <span class="text-secondary text-xs">申请理由:</span>
            <span class="text-secondary text-xs">{{ selectedRequest.reason || '无说明' }}</span>
          </div>
        </div>

        <div class="form-group mt-4">
          <label class="form-label font-medium text-sm">
            {{ currentReviewAction === 'approved' ? '审批批注 (选填)' : '驳回原因说明 (建议填写)' }}
          </label>
          <textarea
            v-model="reviewComment"
            rows="3"
            :placeholder="currentReviewAction === 'approved' ? '如：业务申请合规，准予开通' : '如：功能超出当前工作岗位范围'"
            class="form-textarea"
          ></textarea>
        </div>
      </div>
      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="text" @click="reviewModalVisible = false">取消</MdButton>
          <MdButton
            :variant="currentReviewAction === 'approved' ? 'tonal' : 'outlined'"
            :disabled="submittingReview"
            @click="submitReview"
          >
            <span v-if="submittingReview">正在处理...</span>
            <span v-else>{{ currentReviewAction === 'approved' ? '确认同意开通' : '确认驳回' }}</span>
          </MdButton>
        </div>
      </template>
    </AdaptiveModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  RefreshCw,
  Search,
  ShieldCheck,
  User,
  Check,
  X,
} from 'lucide-vue-next'
import {
  MdButton,
  MdTable,
  MdPagination,
  MdTooltip,
  AdaptiveModal,
  type MdTableColumn
} from '@/components/m3'
import { useToast } from '@/composables/useToast'
import {
  getAdminPermissionRequests,
  reviewAdminPermissionRequest,
  type PermissionRequest,
} from '@/api/portal'

const toast = useToast()

const columns: MdTableColumn[] = [
  { key: 'id', title: '申请单号', width: '150px' },
  { key: 'user_name', title: '申请人', width: '160px' },
  { key: 'service_name', title: '所属 MCP 服务', width: '160px' },
  { key: 'tool_names', title: '申请开通功能', width: '220px' },
  { key: 'reason', title: '业务用途说明' },
  { key: 'status', title: '审批状态', width: '120px', align: 'center' },
  { key: 'created_at', title: '提交时间', width: '160px' },
  { key: 'reviewed_info', title: '审批人 / 批注', width: '180px' },
  { key: 'actions', title: '操作', width: '150px', align: 'center' },
]

const requests = ref<PermissionRequest[]>([])
const loading = ref(false)
const searchKeyword = ref('')
const activeStatusFilter = ref<string>('all')

// 分页状态
const page = ref(1)
const pageSize = ref(15)

// 审批弹窗状态
const reviewModalVisible = ref(false)
const selectedRequest = ref<PermissionRequest | null>(null)
const currentReviewAction = ref<'approved' | 'rejected'>('approved')
const reviewComment = ref('')
const submittingReview = ref(false)

const statusTabs = computed(() => {
  const pendingCount = requests.value.filter(r => r.status === 'pending').length
  const approvedCount = requests.value.filter(r => r.status === 'approved').length
  const rejectedCount = requests.value.filter(r => r.status === 'rejected').length
  return [
    { label: '全部申请', value: 'all', count: requests.value.length },
    { label: '待审批', value: 'pending', count: pendingCount },
    { label: '已通过', value: 'approved', count: approvedCount },
    { label: '已驳回', value: 'rejected', count: rejectedCount },
  ]
})

const filteredRequests = computed(() => {
  return requests.value.filter(item => {
    // 状态过滤
    if (activeStatusFilter.value !== 'all' && item.status !== activeStatusFilter.value) {
      return false
    }
    // 关键字搜索
    if (searchKeyword.value.trim()) {
      const kw = searchKeyword.value.trim().toLowerCase()
      const matchUser = (item.user_id + item.user_name).toLowerCase().includes(kw)
      const matchSvc = (item.service_id + item.service_name).toLowerCase().includes(kw)
      const matchTools = item.tool_names.some(t => t.toLowerCase().includes(kw))
      const matchReason = (item.reason || '').toLowerCase().includes(kw)
      if (!matchUser && !matchSvc && !matchTools && !matchReason) {
        return false
      }
    }
    return true
  })
})

const totalCount = computed(() => filteredRequests.value.length)

const pagedRequests = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRequests.value.slice(start, start + pageSize.value)
})

watch([activeStatusFilter, searchKeyword, pageSize], () => {
  page.value = 1
})

function setStatusFilter(val: string) {
  activeStatusFilter.value = val
}

function formatTime(isoStr?: string | null): string {
  if (!isoStr) return '-'
  try {
    return new Date(isoStr).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return isoStr.slice(0, 19).replace('T', ' ')
  }
}

function formatDayOnly(isoStr?: string | null): string {
  if (!isoStr) return ''
  return isoStr.slice(0, 10)
}

async function loadRequests() {
  loading.value = true
  try {
    requests.value = await getAdminPermissionRequests()
  } catch (err) {
    toast.error('加载权限申请单失败')
  } finally {
    loading.value = false
  }
}

function openReviewModal(item: PermissionRequest, action: 'approved' | 'rejected') {
  selectedRequest.value = item
  currentReviewAction.value = action
  reviewComment.value = action === 'approved' ? '同意开通' : ''
  reviewModalVisible.value = true
}

async function submitReview() {
  if (!selectedRequest.value) return
  submittingReview.value = true
  try {
    await reviewAdminPermissionRequest(selectedRequest.value.id, {
      status: currentReviewAction.value,
      reviewer: 'admin',
      comment: reviewComment.value.trim() || undefined,
    })
    toast.success(
      currentReviewAction.value === 'approved'
        ? `已同意 ${selectedRequest.value.user_name || selectedRequest.value.user_id} 的功能开通申请！`
        : `已驳回申请`
    )
    reviewModalVisible.value = false
    await loadRequests()
  } catch (err) {
    toast.error('审批操作失败，请重试')
  } finally {
    submittingReview.value = false
  }
}

onMounted(() => {
  loadRequests()
})
</script>

<style scoped>
.permissions-view {
  padding: 24px 32px;
  max-width: 1500px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.title-area h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}
.title-area p {
  font-size: 14px;
  color: var(--md-sys-color-on-surface-variant);
  margin-top: 6px;
  max-width: 900px;
  line-height: 1.5;
}

/* 嵌入式工具栏 */
.table-toolbar-inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 16px;
}

.status-tab-group {
  display: flex;
  gap: 6px;
  align-items: center;
}
.tab-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  border: 1px solid transparent;
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.tab-pill-btn:hover {
  background-color: var(--md-sys-color-surface-container-high);
}
.tab-pill-btn.is-active {
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  font-weight: 600;
}
.tab-count-badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  background-color: var(--md-sys-color-surface-container-lowest);
  color: inherit;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 280px;
  height: 36px;
  padding: 0 10px;
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 8px;
}
.search-icon {
  color: var(--md-sys-color-outline);
}
.search-input {
  border: none;
  outline: none;
  background: transparent;
  width: 100%;
  font-size: 13px;
  color: var(--md-sys-color-on-surface);
}
.clear-search-btn {
  border: none;
  background: transparent;
  color: var(--md-sys-color-outline);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 单元格定制样式 */
.mono-code {
  font-family: var(--font-mono, monospace);
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.user-avatar-small {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.user-meta-lines {
  display: flex;
  flex-direction: column;
}
.user-name-text {
  color: var(--md-sys-color-on-surface);
  line-height: 1.2;
}
.user-id-sub {
  line-height: 1.2;
  margin-top: 2px;
}

.service-cell {
  display: flex;
  flex-direction: column;
}

.tools-tags-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.tool-tag {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background-color: var(--md-sys-color-surface-container-high);
  border: 1px solid var(--md-sys-color-outline-variant);
  color: var(--md-sys-color-on-surface);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reason-cell-text {
  color: var(--md-sys-color-on-surface);
}

.status-chip {
  font-size: 12px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
}
.status-chip.status-approved {
  background-color: rgba(34, 197, 94, 0.12);
  color: #16a34a;
  border: 1px solid rgba(34, 197, 94, 0.25);
}
.status-chip.status-rejected {
  background-color: rgba(239, 68, 68, 0.12);
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.25);
}
.status-chip.status-pending {
  background-color: rgba(245, 158, 11, 0.12);
  color: #d97706;
  border: 1px solid rgba(245, 158, 11, 0.25);
}

.reviewed-cell {
  display: flex;
  flex-direction: column;
}

.action-buttons-inline {
  display: flex;
  gap: 8px;
  justify-content: center;
}
.btn-inline-approve {
  background-color: rgba(34, 197, 94, 0.15);
  color: #16a34a;
  border: 1px solid rgba(34, 197, 94, 0.3);
}
.btn-inline-approve:hover {
  background-color: #16a34a;
  color: white;
}
.btn-inline-reject {
  color: #dc2626;
  border-color: rgba(239, 68, 68, 0.3);
}
.btn-inline-reject:hover {
  background-color: rgba(239, 68, 68, 0.1);
}

/* 弹窗定制 */
.modal-summary-card {
  padding: 12px 14px;
  border-radius: 8px;
  background-color: var(--md-sys-color-surface-container-high);
  border: 1px solid var(--md-sys-color-outline-variant);
}
.summary-line {
  display: flex;
  gap: 8px;
  align-items: center;
}
.form-textarea {
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--md-sys-color-outline-variant);
  background-color: var(--md-sys-color-surface-container-lowest);
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  outline: none;
}
.form-textarea:focus {
  border-color: var(--md-sys-color-primary);
}
.modal-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
