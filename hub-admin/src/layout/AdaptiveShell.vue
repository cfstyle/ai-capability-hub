<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard,
  Server,
  Wrench,
  Terminal,
  ScrollText,
  Settings,
  Sun,
  Moon,
  Search,
  Cpu,
  Command,
  PanelLeftClose,
  PanelLeftOpen,
  AlignJustify,
  Rows3,
  Menu,
  LogOut,
  ShieldCheck,
  CheckCircle2,
  ChevronRight,
  Compass
} from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import { MdSwitch, MdDrawer, AdaptiveModal, MdButton, McpLogo } from '@/components/m3'
import { useToast } from '@/composables/useToast'

interface NavItem {
  name: string
  label: string
  path: string
  icon: Component
  badge?: string | number
}

const navItems: NavItem[] = [
  { name: 'dashboard', label: '运行总览', path: '/admin/dashboard', icon: LayoutDashboard },
  { name: 'servers', label: 'MCP 服务', path: '/admin/servers/list', icon: Server },
  { name: 'tools', label: '工具目录', path: '/admin/tools/list', icon: Wrench },
  { name: 'permissions', label: '权限审批', path: '/admin/permissions', icon: ShieldCheck },
  { name: 'debug', label: '在线调试', path: '/admin/tools/debug', icon: Terminal },
  { name: 'audit', label: '调用审计', path: '/admin/audit', icon: ScrollText },
  { name: 'system', label: '系统管理', path: '/admin/system', icon: Settings },
]

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const authStore = useAuthStore()
const toast = useToast()

const searchQuery = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)
const isRailCollapsed = ref(false)
const isMobileDrawerOpen = ref(false)
const showLogoutModal = ref(false)
const showUserMenu = ref(false)

const toggleCollapse = () => {
  isRailCollapsed.value = !isRailCollapsed.value
}

const currentTitle = computed(() => {
  if (route.meta?.title) {
    return route.meta.title as string
  }
  const current = navItems.find((item) => isActive(item.path))
  return current ? current.label : 'Capability Hub'
})

const navigateTo = (path: string) => {
  if (route.path !== path) {
    router.push(path)
  }
}

const navigateAndCloseMobileDrawer = (path: string) => {
  isMobileDrawerOpen.value = false
  navigateTo(path)
}

const isActive = (path: string) => {
  if (path === '/admin/servers/list') {
    return route.path.startsWith('/admin/servers')
  }
  if (path === '/admin/tools/list') {
    return route.path === '/admin/tools/list'
  }
  return route.path === path || route.path.startsWith(path + '/')
}

const handleGlobalKeydown = (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    searchInputRef.value?.focus()
    searchInputRef.value?.select()
  }
}

const handleSearchSubmit = () => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return
  if (query.includes('服务') || query.includes('server')) {
    navigateTo('/admin/servers/list')
  } else if (query.includes('工具') || query.includes('tool')) {
    navigateTo('/admin/tools/list')
  } else if (query.includes('调试') || query.includes('debug')) {
    navigateTo('/admin/tools/debug')
  } else if (query.includes('审计') || query.includes('log') || query.includes('audit')) {
    navigateTo('/admin/audit')
  } else if (query.includes('系统') || query.includes('system')) {
    navigateTo('/admin/system')
  } else {
    // 默认跳转工具目录并作为关键字过滤
    router.push({ path: '/admin/tools/list', query: { q: query } })
  }
  searchQuery.value = ''
}

const confirmLogout = () => {
  authStore.logout()
  showLogoutModal.value = false
  toast.success('已安全退出管理会话')
  router.push('/login')
}

onMounted(() => {
  themeStore.setLayoutContext('admin')
  window.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<template>
  <div class="m3-shell">
    <!-- ====================================================================
         1. 手机端顶部应用栏 (Top App Bar, < 600px)
         ==================================================================== -->
    <header class="m3-mobile-top-bar">
      <div class="m3-mobile-top-bar__start">
        <button
          type="button"
          class="m3-icon-button md-state-layer m3-mobile-menu-btn"
          title="打开侧边导航抽屉"
          aria-label="打开侧边导航抽屉"
          @click="isMobileDrawerOpen = true"
        >
          <Menu :size="22" />
        </button>
        <div class="m3-brand-badge">
          <McpLogo :size="20" />
        </div>
        <h1 class="title-large m3-mobile-top-bar__title">{{ currentTitle }}</h1>
      </div>
      <div class="m3-mobile-top-bar__end">
        <button
          type="button"
          class="m3-icon-button md-state-layer"
          :title="themeStore.isDark ? '切换浅色模式' : '切换深色模式'"
          @click="themeStore.toggleTheme"
        >
          <Sun v-if="themeStore.isDark" :size="20" />
          <Moon v-else :size="20" />
        </button>
      </div>
    </header>

    <!-- ====================================================================
         2. 平板端常驻导航轨 (Navigation Rail, 600px - 839px)
         ==================================================================== -->
    <aside class="m3-nav-rail">
      <div class="m3-nav-rail__header">
        <div class="m3-brand-badge" title="MCP中心 控制台">
          <McpLogo :size="24" />
        </div>
      </div>

      <nav class="m3-nav-rail__items">
        <button
          v-for="item in navItems"
          :key="item.path"
          type="button"
          :class="['m3-rail-btn', { 'is-active': isActive(item.path) }]"
          :title="item.label"
          @click="navigateTo(item.path)"
        >
          <div class="nav-icon-pill md-state-layer">
            <component :is="item.icon" :size="20" />
            <span v-if="item.badge" class="m3-badge rail-badge">{{ item.badge }}</span>
          </div>
          <span class="rail-label">{{ item.label }}</span>
        </button>
      </nav>

      <div class="m3-nav-rail__footer">
        <button
          type="button"
          class="m3-compact-action-btn md-state-layer"
          title="切换深色/浅色主题"
          @click="themeStore.toggleTheme"
        >
          <Sun v-if="themeStore.isDark" :size="20" />
          <Moon v-else :size="20" />
        </button>
        <button
          type="button"
          class="m3-compact-action-btn md-state-layer"
          title="退出登录"
          @click="showLogoutModal = true"
        >
          <LogOut :size="18" />
        </button>
      </div>
    </aside>

    <!-- ====================================================================
         3. PC 宽屏端自适应抽屉 / 可折叠导航轨 (Drawer / Collapsible Rail, >= 840px)
         ==================================================================== -->
    <aside :class="['m3-nav-drawer', { 'is-collapsed': isRailCollapsed }]">
      <!-- 顶部品牌与折叠控制器 -->
      <div class="m3-drawer__header">
        <div class="m3-drawer__brand" @click="navigateTo('/admin/dashboard')">
          <div class="m3-brand-badge">
            <McpLogo :size="24" />
          </div>
          <div v-show="!isRailCollapsed" class="m3-brand-text">
            <span class="title-medium">MCP中心</span>
            <span class="body-small m3-brand-sub">管理控制台</span>
          </div>
        </div>

        <button
          type="button"
          class="m3-collapse-btn md-state-layer"
          :title="isRailCollapsed ? '展开导航抽屉 (256px)' : '折叠为导航轨 (80px)'"
          @click="toggleCollapse"
        >
          <PanelLeftOpen v-if="isRailCollapsed" :size="18" />
          <PanelLeftClose v-else :size="18" />
        </button>
      </div>

      <!-- 导航列表项 -->
      <nav class="m3-drawer__nav">
        <!-- 收起态 (Navigation Rail Mode: 80px 宽度) -->
        <template v-if="isRailCollapsed">
          <button
            v-for="item in navItems"
            :key="item.path"
            type="button"
            :class="['m3-rail-btn', { 'is-active': isActive(item.path) }]"
            :title="item.label"
            @click="navigateTo(item.path)"
          >
            <div class="nav-icon-pill md-state-layer">
              <component :is="item.icon" :size="20" />
              <span v-if="item.badge" class="m3-badge rail-badge">{{ item.badge }}</span>
            </div>
            <span class="rail-label">{{ item.label }}</span>
          </button>
        </template>

        <!-- 展开态 (Navigation Drawer Mode: 256px 宽度) -->
        <template v-else>
          <button
            v-for="item in navItems"
            :key="item.path"
            type="button"
            :class="['m3-drawer-item', 'md-state-layer', { 'is-active': isActive(item.path) }]"
            @click="navigateTo(item.path)"
          >
            <span class="m3-drawer-item__icon">
              <component :is="item.icon" :size="20" />
            </span>
            <span class="m3-drawer-item__label label-large">{{ item.label }}</span>
            <span v-if="item.badge" class="m3-badge drawer-badge">{{ item.badge }}</span>
          </button>
        </template>
      </nav>

      <!-- 抽屉底部操作区 (浅/深色模式切换) -->
      <div class="m3-drawer__footer">
        <template v-if="!isRailCollapsed">
          <div
            class="m3-drawer__theme-switch"
            @click="themeStore.toggleTheme"
          >
            <div class="m3-drawer__theme-info">
              <component :is="themeStore.isDark ? Moon : Sun" :size="20" />
              <span class="label-large">{{ themeStore.isDark ? '深色模式' : '浅色模式' }}</span>
            </div>
            <MdSwitch
              :model-value="themeStore.isDark"
              @click.stop
              @update:model-value="themeStore.toggleTheme"
            >
              <template #checkedIcon><Moon :size="12" /></template>
              <template #uncheckedIcon><Sun :size="12" /></template>
            </MdSwitch>
          </div>
        </template>

        <template v-else>
          <div class="m3-rail-compact-footer">
            <button
              type="button"
              class="m3-compact-action-btn md-state-layer"
              title="切换深色/浅色主题"
              @click="themeStore.toggleTheme"
            >
              <Sun v-if="themeStore.isDark" :size="20" />
              <Moon v-else :size="20" />
            </button>
          </div>
        </template>
      </div>
    </aside>

    <!-- ====================================================================
         4. 主内容视口区
         ==================================================================== -->
    <div :class="['m3-main-container', { 'is-rail-collapsed': isRailCollapsed }]">
      <!-- PC 端及平板端通用 Top Bar -->
      <header class="m3-desktop-top-bar">
        <!-- 胶囊搜索框与面包屑 -->
        <div class="m3-topbar-left">
          <div class="m3-breadcrumb">
            <span class="m3-breadcrumb__item" @click="navigateTo('/admin/dashboard')">控制台</span>
            <ChevronRight :size="14" class="m3-breadcrumb__separator" />
            <span class="m3-breadcrumb__current">{{ currentTitle }}</span>
          </div>

          <div class="m3-search-bar">
            <Search :size="18" class="m3-search-bar__icon" />
            <input
              ref="searchInputRef"
              v-model="searchQuery"
              type="text"
              placeholder="搜索服务、工具或快捷直达... (Ctrl+K)"
              class="m3-search-bar__input body-medium"
              @keyup.enter="handleSearchSubmit"
            />
            <div class="m3-search-bar__shortcut label-small">
              <Command :size="12" /> K
            </div>
          </div>
        </div>

        <!-- 右侧操作区：返回门户 + 就绪状态 + 种子色快切 + 紧凑/舒适密度 + 明暗开关 + 用户头像 -->
        <div class="m3-desktop-top-bar__actions">
          <!-- 返回能力门户 -->
          <button
            type="button"
            class="m3-portal-back-btn md-state-layer"
            title="返回免登录公开能力门户"
            @click="navigateTo('/')"
          >
            <Compass :size="16" />
            <span class="label-medium">能力门户</span>
          </button>

          <!-- 控制面在线状态 Badge -->
          <div class="m3-status-pill" title="Hub Core 核心控制面实时状态正常">
            <span class="m3-status-dot"></span>
            <span class="m3-status-label">控制面正常</span>
          </div>

          <!-- 紧凑/舒适密度切换按钮 -->
          <button
            type="button"
            class="m3-icon-button md-state-layer"
            :title="themeStore.density === 'compact' ? '当前：紧凑密度 (点击切换舒适)' : '当前：舒适密度 (点击切换紧凑)'"
            @click="themeStore.setDensity(themeStore.density === 'compact' ? 'comfortable' : 'compact')"
          >
            <Rows3 v-if="themeStore.density === 'compact'" :size="18" />
            <AlignJustify v-else :size="18" />
          </button>

          <!-- 明暗主题切换按钮 -->
          <button
            type="button"
            class="m3-icon-button md-state-layer"
            :title="themeStore.isDark ? '切换浅色模式' : '切换深色模式'"
            @click="themeStore.toggleTheme"
          >
            <Sun v-if="themeStore.isDark" :size="19" />
            <Moon v-else :size="19" />
          </button>

          <div class="m3-topbar-divider"></div>

          <!-- 用户操作区 -->
          <div class="m3-user-dropdown-area">
            <div
              class="m3-avatar-wrapper md-state-layer"
              title="管理员账号"
              @click="showUserMenu = !showUserMenu"
            >
              <div class="m3-avatar">
                <span>{{ (authStore.username || 'AD').slice(0, 2).toUpperCase() }}</span>
              </div>
              <span class="m3-username body-medium">{{ authStore.username || '管理员' }}</span>
            </div>

            <!-- 浮动操作卡片 -->
            <div v-if="showUserMenu" class="m3-user-popover" @click="showUserMenu = false">
              <div class="m3-user-popover__header">
                <ShieldCheck :size="18" class="text-primary" />
                <div class="user-meta">
                  <div class="user-name">{{ authStore.username || '管理员' }}</div>
                  <div class="user-role body-small">超级管理凭据</div>
                </div>
              </div>
              <div class="m3-user-popover__divider"></div>
              <button class="m3-popover-item md-state-layer" @click="navigateTo('/system')">
                <Settings :size="16" />
                <span>系统管理与凭据</span>
              </button>
              <button class="m3-popover-item is-danger md-state-layer" @click="showLogoutModal = true">
                <LogOut :size="16" />
                <span>退出登录</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <!-- 实际页面视图挂载点 -->
      <main class="m3-content-wrapper">
        <div class="m3-content-constrain">
          <router-view />
        </div>
      </main>
    </div>

    <!-- ====================================================================
         5. 手机端底部导航栏 (Navigation Bar, < 600px)
         ==================================================================== -->
    <nav class="m3-bottom-nav">
      <button
        v-for="item in navItems.slice(0, 5)"
        :key="item.path"
        type="button"
        :class="['m3-nav-bar-item', { 'is-active': isActive(item.path) }]"
        @click="navigateTo(item.path)"
      >
        <div class="m3-nav-indicator md-state-layer">
          <component :is="item.icon" :size="20" />
          <span v-if="item.badge" class="m3-badge m3-badge--small">{{ item.badge }}</span>
        </div>
        <span class="m3-nav-bar-item__label label-medium">{{ item.label }}</span>
      </button>
    </nav>

    <!-- ====================================================================
         6. 移动端侧边抽屉
         ==================================================================== -->
    <MdDrawer
      v-model="isMobileDrawerOpen"
      title="控制台导航"
      width="300px"
    >
      <div class="m3-mobile-drawer-body">
        <div class="m3-mobile-drawer-brand" @click="navigateAndCloseMobileDrawer('/dashboard')">
          <div class="m3-brand-badge">
            <McpLogo :size="20" />
          </div>
          <div class="m3-brand-text">
            <span class="title-medium">MCP中心</span>
            <span class="body-small text-secondary">管理控制台</span>
          </div>
        </div>

        <nav class="m3-mobile-drawer-nav">
          <button
            v-for="item in navItems"
            :key="item.path"
            type="button"
            :class="['m3-drawer-item', 'md-state-layer', { 'is-active': isActive(item.path) }]"
            @click="navigateAndCloseMobileDrawer(item.path)"
          >
            <span class="m3-drawer-item__icon">
              <component :is="item.icon" :size="20" />
            </span>
            <span class="m3-drawer-item__label label-large">{{ item.label }}</span>
            <span v-if="item.badge" class="m3-badge drawer-badge">{{ item.badge }}</span>
          </button>
        </nav>

        <div class="m3-mobile-drawer-footer">
          <div
            class="m3-drawer__theme-switch"
            @click="themeStore.toggleTheme"
          >
            <div class="m3-drawer__theme-info">
              <component :is="themeStore.isDark ? Moon : Sun" :size="20" />
              <span class="label-large">{{ themeStore.isDark ? '深色模式' : '浅色模式' }}</span>
            </div>
            <MdSwitch
              :model-value="themeStore.isDark"
              @click.stop
              @update:model-value="themeStore.toggleTheme"
            >
              <template #checkedIcon><Moon :size="12" /></template>
              <template #uncheckedIcon><Sun :size="12" /></template>
            </MdSwitch>
          </div>

          <button
            type="button"
            class="m3-mobile-logout-btn md-state-layer"
            @click="isMobileDrawerOpen = false; showLogoutModal = true"
          >
            <LogOut :size="18" />
            <span>退出当前登录</span>
          </button>
        </div>
      </div>
    </MdDrawer>

    <!-- ====================================================================
         7. 退出登录确认弹窗 (AdaptiveModal)
         ==================================================================== -->
    <AdaptiveModal
      v-model="showLogoutModal"
      title="确认退出管理控制台"
      width="440px"
    >
      <div class="logout-confirm-content">
        <p class="body-large">退出登录将清除当前本地浏览器中缓存的管理员 API Key 凭据，确认继续吗？</p>
      </div>
      <template #footer>
        <div class="modal-actions">
          <MdButton variant="text" @click="showLogoutModal = false">取消</MdButton>
          <MdButton variant="tonal" class="btn-danger" @click="confirmLogout">确认退出</MdButton>
        </div>
      </template>
    </AdaptiveModal>
  </div>
</template>

<style scoped>
.m3-shell {
  display: flex;
  min-height: 100vh;
  width: 100%;
  background-color: var(--md-sys-color-surface);
  position: relative;
}

/* ================= 通用原子装饰 ================= */
.m3-brand-badge {
  width: 36px;
  height: 36px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  background: linear-gradient(135deg, var(--md-sys-color-primary), var(--md-sys-color-tertiary));
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--md-sys-elevation-level1);
  flex-shrink: 0;
}

.m3-icon-button {
  width: 40px;
  height: 40px;
  border-radius: var(--md-sys-shape-corner-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--md-sys-color-on-surface-variant);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: color var(--md-sys-motion-duration-short2) var(--md-sys-motion-easing-standard);
}
.m3-icon-button:hover {
  color: var(--md-sys-color-on-surface);
}

/* 消息角标 */
.m3-badge {
  position: absolute;
  padding: 0 4px;
  border-radius: var(--md-sys-shape-corner-full);
  background-color: var(--md-sys-color-error);
  color: var(--md-sys-color-on-error);
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

.m3-badge--small {
  top: 4px;
  right: 14px;
  min-width: 18px;
  height: 18px;
  font-size: var(--md-type-meta-size, 12px);
}

.drawer-badge {
  position: static;
  min-width: 18px;
  height: 18px;
  font-size: var(--md-type-meta-size, 12px);
  line-height: 18px;
  margin-left: auto;
}

.rail-badge {
  top: 2px;
  right: 10px;
  min-width: 16px;
  height: 16px;
  font-size: var(--md-type-meta-size, 12px);
  line-height: 16px;
}

/* ================= 1. 手机端顶部应用栏 ================= */
.m3-mobile-top-bar {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  background-color: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface);
  padding: 0 16px;
  z-index: 30;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--md-sys-color-surface-container-high);
}

.m3-mobile-top-bar__start {
  display: flex;
  align-items: center;
  gap: 12px;
}

.m3-mobile-menu-btn {
  display: inline-flex;
  margin-right: -4px;
}

/* ================= 2. 平板端常驻导航轨 (Navigation Rail) ================= */
.m3-nav-rail {
  display: none;
  width: 80px;
  height: 100vh;
  position: fixed;
  top: 0;
  left: 0;
  background-color: var(--md-sys-color-surface);
  border-right: 1px solid var(--md-sys-color-outline-variant);
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: 20px 0;
  z-index: 30;
}

.m3-nav-rail__header {
  margin-bottom: 24px;
}

.m3-nav-rail__items {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
  flex: 1;
}

.m3-nav-rail__footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

/* ================= 3. PC 导航抽屉 / 折叠导航轨 ================= */
.m3-nav-drawer {
  display: none;
  width: 256px;
  height: 100vh;
  position: fixed;
  top: 0;
  left: 0;
  background-color: var(--md-sys-color-surface-container-low);
  border-right: 1px solid var(--md-sys-color-outline-variant);
  flex-direction: column;
  padding: 20px 16px;
  z-index: 30;
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.25s cubic-bezier(0.2, 0, 0, 1),
              padding 0.25s cubic-bezier(0.2, 0, 0, 1);
}

.m3-nav-drawer.is-collapsed {
  width: 80px;
  padding: 20px 6px;
  align-items: center;
}

.m3-drawer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px 20px 8px;
  width: 100%;
}

.m3-nav-drawer.is-collapsed .m3-drawer__header {
  flex-direction: column;
  gap: 12px;
  padding: 0 0 20px 0;
  align-items: center;
}

.m3-drawer__brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  user-select: none;
}

.m3-nav-drawer.is-collapsed .m3-drawer__brand .m3-brand-badge {
  width: 40px;
  height: 40px;
}

.m3-brand-text {
  display: flex;
  flex-direction: column;
}

.m3-brand-sub {
  color: var(--md-sys-color-on-surface-variant);
}

.m3-collapse-btn {
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
  transition: color var(--md-sys-motion-duration-short2) var(--md-sys-motion-easing-standard);
}
.m3-collapse-btn:hover {
  color: var(--md-sys-color-on-surface);
}

.m3-drawer__nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  width: 100%;
}

.m3-nav-drawer.is-collapsed .m3-drawer__nav {
  align-items: center;
  gap: 10px;
}

/* 展开态抽屉项样式 */
.m3-drawer-item {
  position: relative;
  height: 48px;
  border-radius: var(--md-sys-shape-corner-full);
  display: flex;
  align-items: center;
  padding: 0 16px 0 16px;
  gap: 14px;
  color: var(--md-sys-color-on-surface-variant);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard);
  width: 100%;
}

.m3-drawer-item:hover {
  color: var(--md-sys-color-on-surface);
}

.m3-drawer-item.is-active {
  background-color: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
  font-weight: 600;
}

.m3-drawer-item__icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.m3-drawer-item__label {
  flex: 1;
  text-align: left;
}

/* 收起态 Rail 项样式 */
.m3-rail-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
  width: 68px;
  background: transparent;
  border: none;
  cursor: pointer;
  user-select: none;
}

.nav-icon-pill {
  width: 56px;
  height: 32px;
  border-radius: var(--md-sys-shape-corner-full);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  color: var(--md-sys-color-on-surface-variant);
  background-color: transparent;
  transition: all var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard);
}

.m3-rail-btn.is-active .nav-icon-pill {
  background-color: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
}

.rail-label {
  font-size: 12px;
  line-height: 16px;
  color: var(--md-sys-color-on-surface-variant);
  font-weight: 500;
}

.m3-rail-btn.is-active .rail-label {
  color: var(--md-sys-color-on-surface);
  font-weight: 600;
}

/* 底部操作区 */
.m3-drawer__footer {
  padding-top: 16px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  display: flex;
  flex-direction: column;
  width: 100%;
}

.m3-nav-drawer.is-collapsed .m3-drawer__footer {
  align-items: center;
}

.m3-drawer__theme-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-radius: var(--md-sys-shape-corner-large);
  background-color: var(--md-sys-color-surface-container);
  cursor: pointer;
  user-select: none;
}

.m3-drawer__theme-info {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--md-sys-color-on-surface);
}

.m3-rail-compact-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.m3-compact-action-btn {
  width: 44px;
  height: 44px;
  border-radius: var(--md-sys-shape-corner-medium, 14px);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--md-sys-color-on-surface-variant);
  background-color: var(--md-sys-color-surface-container);
  border: none;
  cursor: pointer;
  transition: all var(--md-sys-motion-duration-short2) var(--md-sys-motion-easing-standard);
}

.m3-compact-action-btn:hover {
  color: var(--md-sys-color-on-surface);
  background-color: var(--md-sys-color-surface-container-high);
}

/* ================= 4. 主内容与 Top Bar ================= */
.m3-main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-width: 0;
  transition: margin-left 0.25s cubic-bezier(0.2, 0, 0, 1);
}

.m3-desktop-top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 70px;
  padding: 0 32px;
  background-color: var(--md-sys-color-surface);
  position: sticky;
  top: 0;
  z-index: 30;
  border-bottom: 1px solid var(--md-sys-color-surface-container-high);
}

.m3-topbar-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.m3-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 14px;
}

.m3-breadcrumb__item {
  cursor: pointer;
}
.m3-breadcrumb__item:hover {
  color: var(--md-sys-color-primary);
}

.m3-breadcrumb__separator {
  opacity: 0.6;
}

.m3-breadcrumb__current {
  color: var(--md-sys-color-on-surface);
  font-weight: 600;
}

.m3-search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 280px;
  height: 44px;
  background-color: var(--md-sys-color-surface-container-high);
  border-radius: var(--md-sys-shape-corner-full);
  padding: 0 16px;
  color: var(--md-sys-color-on-surface-variant);
  transition: all var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard);
}

.m3-search-bar:focus-within {
  width: 340px;
  box-shadow: var(--md-sys-elevation-level2);
  background-color: var(--md-sys-color-surface-container-highest);
  color: var(--md-sys-color-on-surface);
}

.m3-search-bar__input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--md-sys-color-on-surface);
}

.m3-search-bar__shortcut {
  display: flex;
  align-items: center;
  gap: 2px;
  background-color: var(--md-sys-color-surface-container);
  padding: 2px 6px;
  border-radius: var(--md-sys-shape-corner-small);
  color: var(--md-sys-color-on-surface-variant);
}

.m3-desktop-top-bar__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.m3-portal-back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background-color: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-full);
  color: var(--md-sys-color-primary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard);
}

.m3-portal-back-btn:hover {
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  border-color: var(--md-sys-color-primary);
}

/* 控制面健康胶囊 */
.m3-status-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background-color: var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-full);
  font-size: 13px;
  font-weight: 500;
  color: var(--md-sys-color-on-surface);
}

.m3-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #198754;
  box-shadow: 0 0 0 2px rgba(25, 135, 84, 0.2);
}

/* 6色 HCT 种子色气泡 */
.m3-seed-picker {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-radius: var(--md-sys-shape-corner-full);
  background-color: var(--md-sys-color-surface-container-low);
}

.m3-seed-dot {
  width: 18px;
  height: 18px;
  border-radius: var(--md-sys-shape-corner-full);
  border: none;
  box-shadow: inset 0 0 0 1px var(--md-sys-color-outline-variant);
  cursor: pointer;
  transition: transform var(--md-sys-motion-duration-short2) var(--md-sys-motion-easing-standard),
              box-shadow var(--md-sys-motion-duration-short2) var(--md-sys-motion-easing-standard);
  position: relative;
  flex-shrink: 0;
  outline: none;
}

.m3-seed-dot:hover {
  transform: scale(1.15);
}

.m3-seed-dot.is-active {
  transform: scale(1.15);
  box-shadow: 0 0 0 2px var(--md-sys-color-surface), 0 0 0 4px var(--md-sys-color-primary), inset 0 0 0 1px var(--md-sys-color-outline-variant);
  z-index: 2;
}

.m3-topbar-divider {
  width: 1px;
  height: 24px;
  background-color: var(--md-sys-color-outline-variant);
  margin: 0 4px;
}

/* 用户操作区与浮层 */
.m3-user-dropdown-area {
  position: relative;
}

.m3-avatar-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 10px 4px 4px;
  border-radius: var(--md-sys-shape-corner-full);
  cursor: pointer;
  background-color: var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
  transition: background-color var(--md-sys-motion-duration-short2) var(--md-sys-motion-easing-standard);
}

.m3-avatar-wrapper:hover {
  background-color: var(--md-sys-color-surface-container);
}

.m3-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--md-sys-shape-corner-full);
  background: linear-gradient(135deg, var(--md-sys-color-primary), var(--md-sys-color-tertiary));
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 12px;
}

.m3-username {
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}

.m3-user-popover {
  position: absolute;
  top: 48px;
  right: 0;
  width: 200px;
  background-color: var(--md-sys-color-surface-container-high);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-medium, 16px);
  box-shadow: var(--md-sys-elevation-level3);
  padding: 8px;
  display: flex;
  flex-direction: column;
  z-index: 50;
}

.m3-user-popover__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
}

.m3-user-popover__divider {
  height: 1px;
  background-color: var(--md-sys-color-outline-variant);
  margin: 4px 0;
}

.m3-popover-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--md-sys-shape-corner-small, 8px);
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  cursor: pointer;
  border: none;
  background: transparent;
  width: 100%;
  text-align: left;
}

.m3-popover-item:hover {
  background-color: var(--md-sys-color-surface-container-highest);
}

.m3-popover-item.is-danger {
  color: var(--md-sys-color-error);
}

.m3-content-wrapper {
  flex: 1;
  padding: 24px 32px 48px 32px;
}

.m3-content-constrain {
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* ================= 5. 手机底部导航栏 ================= */
.m3-bottom-nav {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 80px;
  background-color: var(--md-sys-color-surface-container);
  border-top: 1px solid var(--md-sys-color-outline-variant);
  padding-bottom: env(safe-area-inset-bottom, 0);
  z-index: 30;
  align-items: center;
  justify-content: space-around;
}

/* ================= 6. 移动端侧边抽屉内部结构 ================= */
.m3-mobile-drawer-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}

.m3-mobile-drawer-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
}

.m3-mobile-drawer-nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.m3-mobile-drawer-footer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  margin-top: auto;
}

.m3-mobile-logout-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 44px;
  border-radius: var(--md-sys-shape-corner-full);
  background-color: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
  font-weight: 600;
  border: none;
  cursor: pointer;
}

.m3-nav-bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 0;
}

.m3-nav-indicator {
  position: relative;
  width: 64px;
  height: 32px;
  border-radius: var(--md-sys-shape-corner-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--md-sys-color-on-surface-variant);
  transition: all var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard);
}

.m3-nav-bar-item.is-active .m3-nav-indicator {
  background-color: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
}

.m3-nav-bar-item__label {
  color: var(--md-sys-color-on-surface-variant);
}

.m3-nav-bar-item.is-active .m3-nav-bar-item__label {
  color: var(--md-sys-color-on-surface);
  font-weight: 700;
}

/* 退出弹窗 */
.logout-confirm-content {
  padding: 8px 0 16px 0;
  color: var(--md-sys-color-on-surface-variant);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-danger {
  --btn-bg: var(--md-sys-color-error);
  --btn-fg: var(--md-sys-color-on-error);
  background-color: var(--md-sys-color-error) !important;
  color: var(--md-sys-color-on-error) !important;
}

/* ==========================================================================
   自适应响应式断点规则
   ========================================================================== */

/* 手机端: < 600px */
@media (max-width: 599.98px) {
  .m3-mobile-top-bar {
    display: flex;
  }
  .m3-bottom-nav {
    display: flex;
  }
  .m3-desktop-top-bar {
    display: none;
  }
  .m3-nav-rail,
  .m3-nav-drawer {
    display: none;
  }
  .m3-main-container {
    margin-left: 0 !important;
    padding-top: 64px;
    padding-bottom: 80px;
  }
  .m3-content-wrapper {
    padding: 16px 16px 32px 16px;
  }
}

/* 平板端: 600px - 839px */
@media (min-width: 600px) and (max-width: 839.98px) {
  .m3-nav-rail {
    display: flex;
  }
  .m3-main-container {
    margin-left: 80px !important;
  }
  .m3-desktop-top-bar {
    display: flex;
    padding: 0 20px;
  }
  .m3-content-wrapper {
    padding: 16px 20px 36px 20px;
  }
}

/* PC 宽屏端: >= 840px */
@media (min-width: 840px) {
  .m3-nav-drawer {
    display: flex;
  }
  .m3-main-container {
    margin-left: 256px;
  }
  .m3-main-container.is-rail-collapsed {
    margin-left: 80px;
  }
  .m3-desktop-top-bar {
    display: flex;
  }
}

@media (max-width: 1023.98px) {
  .m3-desktop-top-bar {
    padding: 0 16px;
    gap: 12px;
  }
  .m3-search-bar {
    display: none;
  }
}
</style>
