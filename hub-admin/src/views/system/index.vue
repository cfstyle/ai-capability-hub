<template>
  <div class="system-page">
    <div class="page-header">
      <div class="title-area">
        <h1 class="type-title-lg">系统管理与运行状态</h1>
        <p class="type-body-sm text-secondary">查看 Hub Core 控制面就绪状态、健康探针、持久化存储及当前凭据权限</p>
      </div>
      <MdButton variant="tonal" :disabled="loading" @click="fetchStatus">
        <RefreshCw :size="16" :class="{ 'is-spinning': loading }" />
        <span>重新检查探针</span>
      </MdButton>
    </div>

    <div class="system-grid">
      <!-- 1. Hub Core 运行状态探针卡片 -->
      <MdCard variant="elevated" class="info-card">
        <div class="card-header-row">
          <div class="title-with-icon">
            <Activity :size="20" class="text-primary" />
            <h2 class="type-title-md">Hub Core 控制面探针</h2>
          </div>
          <span
            :class="[
              'chip-pill',
              healthStatus === 'ok' ? 'chip-active' : 'chip-error'
            ]"
          >
            {{ healthStatus.toUpperCase() }}
          </span>
        </div>

        <div class="meta-list">
          <div class="meta-row">
            <span class="label-medium text-secondary">系统名称</span>
            <span class="label-large">{{ statusData.hub_name }}</span>
          </div>

          <div class="meta-row">
            <span class="label-medium text-secondary">核心版本</span>
            <span class="body-medium mono-font">v{{ statusData.hub_version }}</span>
          </div>

          <div class="meta-row">
            <span class="label-medium text-secondary">存活探针 (/healthz)</span>
            <div class="probe-result">
              <span :class="['probe-dot', healthStatus === 'ok' ? 'is-healthy' : 'is-error']"></span>
              <span class="body-small font-semibold">{{ healthStatus === 'ok' ? 'Healthy (200 OK)' : 'Failed' }}</span>
            </div>
          </div>

          <div class="meta-row">
            <span class="label-medium text-secondary">就绪探针 (/readyz)</span>
            <div class="probe-result">
              <span :class="['probe-dot', readyStatus === 'ready' ? 'is-healthy' : 'is-error']"></span>
              <span class="body-small font-semibold">
                {{ readyStatus === 'ready' ? 'Ready (Database Connected)' : readyStatus }}
              </span>
            </div>
          </div>

          <div class="meta-row">
            <span class="label-medium text-secondary">MCP Gateway 端点</span>
            <span class="mono-code">{{ statusData.mcp_endpoint }}</span>
          </div>

          <div class="meta-row">
            <span class="label-medium text-secondary">持久化存储</span>
            <div class="storage-info">
              <Database :size="16" class="text-secondary" />
              <span class="body-medium">{{ statusData.database }}</span>
            </div>
          </div>

          <div class="meta-row">
            <span class="label-medium text-secondary">已挂载上游服务数</span>
            <span class="label-large text-primary">{{ statusData.upstream_services_count }} 个服务</span>
          </div>
        </div>
      </MdCard>

      <!-- 2. 当前管理员凭据与会话 -->
      <MdCard variant="elevated" class="info-card">
        <div class="card-header-row">
          <div class="title-with-icon">
            <ShieldCheck :size="20" class="text-secondary" />
            <h2 class="type-title-md">当前管理员凭据与会话</h2>
          </div>
        </div>

        <div class="meta-list">
          <div class="meta-row">
            <span class="label-medium text-secondary">操作员标识</span>
            <div class="user-chip">
              <User :size="16" class="text-primary" />
              <span class="label-large">{{ authStore.username || 'admin' }}</span>
            </div>
          </div>

          <div class="meta-row">
            <span class="label-medium text-secondary">授权通信协议</span>
            <span class="chip-pill chip-inactive">X-API-Key / Bearer Token</span>
          </div>

          <div class="meta-row">
            <span class="label-medium text-secondary">凭据摘要</span>
            <div class="key-box">
              <KeyRound :size="16" class="text-secondary" />
              <span class="mono-code">{{ maskedApiKey }}</span>
            </div>
          </div>

          <div class="meta-row full-row">
            <span class="label-medium text-secondary">授权 Scope 权限范围</span>
            <div class="scopes-wrap">
              <span class="chip-pill chip-active">hub:admin</span>
              <span class="chip-pill chip-active">hub:services:write</span>
              <span class="chip-pill chip-active">hub:tools:call</span>
            </div>
          </div>
        </div>

        <div class="auth-footer">
          <MdButton variant="tonal" class="btn-logout" @click="showLogoutModal = true">
            <LogOut :size="16" />
            <span>退出当前管理会话</span>
          </MdButton>
        </div>
      </MdCard>
    </div>

    <!-- 退出确认模态框 (AdaptiveModal) -->
    <AdaptiveModal
      v-model="showLogoutModal"
      title="退出会话确认"
      width="440px"
    >
      <p class="body-large logout-dialog-text">
        退出会话将从本地缓存中彻底清除管理员凭据 API Key。确认立即登出吗？
      </p>
      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="text" @click="showLogoutModal = false">取消</MdButton>
          <MdButton variant="tonal" class="btn-danger" @click="handleLogout">确认登出</MdButton>
        </div>
      </template>
    </AdaptiveModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  RefreshCw,
  Activity,
  ShieldCheck,
  Database,
  User,
  KeyRound,
  LogOut
} from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { getHealthz, getReadyz, getSystemStatus } from '@/api/system'
import type { SystemStatus } from '@/api/types'
import { MdCard, MdButton, AdaptiveModal } from '@/components/m3'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const authStore = useAuthStore()
const toast = useToast()

const loading = ref(false)
const showLogoutModal = ref(false)
const healthStatus = ref('ok')
const readyStatus = ref('ready')

const statusData = ref<SystemStatus>({
  hub_name: 'AI Capability Hub',
  hub_version: '0.3.0',
  status: 'ok',
  database: 'SQLite (data/hub.db)',
  mcp_endpoint: '/mcp',
  upstream_services_count: 0,
})

const maskedApiKey = computed(() => {
  const k = authStore.apiKey
  if (!k) return '未配置'
  if (k.length <= 6) return '******'
  return `${k.slice(0, 3)}****${k.slice(-3)}`
})

async function fetchStatus() {
  loading.value = true
  try {
    const [h, r, s] = await Promise.all([
      getHealthz().catch(() => ({ status: 'error' })),
      getReadyz().catch((e: Error) => ({ status: `error: ${e.message}` })),
      getSystemStatus(),
    ])
    healthStatus.value = h.status
    readyStatus.value = r.status
    statusData.value = s
    toast.success('探针状态已更新')
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`探针探测异常: ${error.message || '网络错误'}`)
  } finally {
    loading.value = false
  }
}

function handleLogout() {
  authStore.logout()
  showLogoutModal.value = false
  toast.success('已安全退出会话')
  router.push('/login')
}

onMounted(() => {
  fetchStatus()
})
</script>

<style scoped>
.system-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
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

.system-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

@media (max-width: 900px) {
  .system-grid {
    grid-template-columns: 1fr;
  }
}

.info-card {
  padding: 24px;
  border-radius: var(--md-sys-shape-corner-medium, 16px);
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chip-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: var(--md-sys-shape-corner-full, 9999px);
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
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

.meta-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* 扁平键值行 (去掉卡片内嵌套的小灰框) */
.meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  background-color: transparent;
  border: none;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.meta-row:last-child {
  border-bottom: none;
}

.meta-row.full-row {
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.probe-result {
  display: flex;
  align-items: center;
  gap: 8px;
}

.probe-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.probe-dot.is-healthy {
  background-color: #198754;
  box-shadow: 0 0 0 3px rgba(25, 135, 84, 0.2);
}

.probe-dot.is-error {
  background-color: var(--md-sys-color-error);
  box-shadow: 0 0 0 3px rgba(186, 26, 26, 0.2);
}

.storage-info,
.user-chip,
.key-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.scopes-wrap {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.mono-font {
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.auth-footer {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  display: flex;
  justify-content: flex-end;
}

.btn-logout {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-danger {
  background-color: var(--md-sys-color-error) !important;
  color: var(--md-sys-color-on-error) !important;
}

.logout-dialog-text {
  padding: 12px 0;
  color: var(--md-sys-color-on-surface-variant);
}

.modal-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
