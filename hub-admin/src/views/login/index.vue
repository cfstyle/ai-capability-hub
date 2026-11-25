<template>
  <div class="login-wrapper">
    <!-- 顶部极简主题控制条 -->
    <header class="login-topbar">
      <div class="brand-chip">
        <McpLogo :size="20" />
        <span class="label-medium">MCP中心</span>
      </div>
      <div class="topbar-actions">
        <!-- 返回能力门户 -->
        <router-link to="/" class="portal-link label-medium">
          <Compass :size="16" />
          <span>返回能力门户</span>
        </router-link>
        <!-- 明暗切换 -->
        <button
          type="button"
          class="icon-btn md-state-layer"
          :title="themeStore.isDark ? '切换浅色' : '切换深色'"
          @click="themeStore.toggleTheme"
        >
          <Sun v-if="themeStore.isDark" :size="18" />
          <Moon v-else :size="18" />
        </button>
      </div>
    </header>

    <!-- 居中 M3 登录卡片 -->
    <main class="login-main">
      <MdCard variant="elevated" class="login-card">
        <div class="login-header">
          <div class="logo-badge">
            <McpLogo :size="36" animated />
          </div>
          <h1 class="type-title-lg">MCP中心</h1>
          <p class="type-body-sm text-secondary">管理控制台安全登录</p>
        </div>

        <form class="login-form" @submit.prevent="handleLogin">
          <div class="form-group">
            <label class="label-medium" for="apiKey">管理员 API Key</label>
            <MdInput
              id="apiKey"
              v-model="form.apiKey"
              type="password"
              placeholder="HUB_ADMIN_API_KEY（开发默认 dev-admin-key）"
              size="sm"
            >
              <template #prefix>
                <KeyRound :size="16" class="text-secondary" />
              </template>
            </MdInput>
          </div>

          <div class="form-group">
            <label class="label-medium" for="username">操作员标识</label>
            <MdInput
              id="username"
              v-model="form.username"
              type="text"
              placeholder="例如: admin / qa"
              size="sm"
            >
              <template #prefix>
                <User :size="16" class="text-secondary" />
              </template>
            </MdInput>
          </div>

          <MdButton
            type="submit"
            variant="tonal"
            class="submit-btn"
            :disabled="loading"
          >
            <span v-if="!loading">登 录 控 制 台</span>
            <span v-else>正在验证凭据...</span>
          </MdButton>
        </form>

        <div class="login-footer">
          <p class="type-body-sm text-secondary">
            未设置密钥的环境将以本地管理员权限直接连接后端
          </p>
        </div>
      </MdCard>
    </main>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Cpu, KeyRound, User, Sun, Moon, Compass } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { MdCard, MdButton, MdInput, McpLogo } from '@/components/m3'
import { listServices } from '@/api/server'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const toast = useToast()

const loading = ref(false)

const form = reactive({
  apiKey: authStore.apiKey || 'dev-admin-key',
  username: authStore.username || 'admin',
})

async function handleLogin() {
  if (!form.apiKey.trim() || !form.username.trim()) {
    toast.warning('请输入管理员 API Key 和操作员标识')
    return
  }

  loading.value = true
  authStore.setApiKey(form.apiKey.trim(), form.username.trim())

  try {
    // 探测后端服务状态并校验凭据
    await listServices()
    toast.success('登录成功，欢迎进入 Capability Hub')
    const redirectUrl = (route.query.redirect as string) || '/admin/dashboard'
    router.push(redirectUrl)
  } catch (err: unknown) {
    const error = err as { response?: { status?: number; data?: { detail?: string } }; message?: string }
    if (error.response?.status === 500) {
      toast.error('无法连接到 Hub Core 后端 (127.0.0.1:8080)，请先确认后端已启动！')
    } else {
      const msg = error.response?.data?.detail || error.message || '未知异常'
      toast.error(`认证失败: ${msg}`)
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  width: 100vw;
  background-color: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface);
  display: flex;
  flex-direction: column;
}

.login-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  height: 64px;
}

.brand-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.portal-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--md-sys-color-primary);
  text-decoration: none;
  padding: 6px 12px;
  border-radius: 9999px;
  background-color: var(--md-sys-color-surface-container);
  transition: all 0.2s ease;
}

.portal-link:hover {
  background-color: var(--md-sys-color-surface-container-high);
}

.seed-dots {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background-color: var(--md-sys-color-surface-container-low);
  border-radius: var(--md-sys-shape-corner-full);
}

.seed-dot {
  width: 18px;
  height: 18px;
  border-radius: var(--md-sys-shape-corner-full);
  border: none;
  box-shadow: inset 0 0 0 1px var(--md-sys-color-outline-variant);
  cursor: pointer;
  transition: transform var(--md-sys-motion-duration-short2) var(--md-sys-motion-easing-standard);
}

.seed-dot.is-active {
  transform: scale(1.15);
  box-shadow: 0 0 0 2px var(--md-sys-color-surface), 0 0 0 4px var(--md-sys-color-primary);
}

.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--md-sys-shape-corner-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--md-sys-color-on-surface-variant);
  background: transparent;
  border: none;
  cursor: pointer;
}

.login-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 440px;
  padding: 36px 32px;
  border-radius: var(--md-sys-shape-corner-extra-large, 28px);
  background-color: var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.login-header {
  text-align: center;
  margin-bottom: 28px;
}

.logo-badge {
  width: 56px;
  height: 56px;
  border-radius: var(--md-sys-shape-corner-large, 18px);
  background: linear-gradient(135deg, var(--md-sys-color-primary), var(--md-sys-color-tertiary));
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  box-shadow: var(--md-sys-elevation-level2);
}

.text-secondary {
  color: var(--md-sys-color-on-surface-variant);
  margin-top: 6px;
}

.text-primary {
  color: var(--md-sys-color-primary);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.submit-btn {
  width: 100%;
  height: 40px;
  margin-top: 8px;
  font-size: 14px;
}

.login-footer {
  margin-top: 24px;
  text-align: center;
  padding-top: 16px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
}
</style>
