<template>
  <div class="portal-root">
    <!-- ====================================================================
         1. 顶部全局导航栏 (Top Navigation Bar)
         ==================================================================== -->
    <header class="portal-header">
      <div class="portal-header__inner">
        <!-- 品牌标识 -->
        <div class="brand-group" title="返回能力中心首页" @click="resetFilters">
          <McpLogo :size="32" animated />
          <div class="brand-text">
            <span class="brand-title">MCP中心</span>
            <span class="brand-badge">HUB</span>
          </div>
        </div>

        <!-- 中间：全局搜索栏 (Ctrl+K / ⌘K) -->
        <div class="header-search">
          <Search :size="18" class="search-icon" />
          <input
            ref="searchInputRef"
            v-model="searchKeyword"
            type="text"
            placeholder="搜业务场景、能力服务或工具... (Ctrl+K)"
            class="search-input"
            @input="handleSearchInput"
          />
          <button
            v-if="searchKeyword"
            type="button"
            class="search-clear-btn"
            title="清空搜索"
            @click="clearSearch"
          >
            <X :size="14" />
          </button>
          <div class="search-shortcut">
            <span>{{ isMac ? '⌘' : 'Ctrl' }}</span>
            <span>K</span>
          </div>
        </div>

        <!-- 右侧操作区：极简清爽结构 -->
        <div class="header-actions">
          <!-- 全局一键接入 (核心快捷入口) -->
          <button
            type="button"
            class="action-btn global-access-btn"
            title="一键将平台能力接入本地 AI Harness"
            @click="handleAccessClick()"
          >
            <Zap :size="15" />
            <span>一键接入</span>
          </button>

          <!-- 浅色/深色模式切换 -->
          <button
            type="button"
            class="icon-action-btn"
            :title="themeStore.isDark ? '切换浅色模式' : '切换深色模式'"
            @click="themeStore.toggleTheme"
          >
            <Sun v-if="themeStore.isDark" :size="18" />
            <Moon v-else :size="18" />
          </button>

          <div class="header-divider"></div>

          <!-- 未登录状态：工号快捷登录按钮 -->
          <button
            v-if="!isLoggedIn"
            type="button"
            class="action-btn login-btn"
            title="输入企业工号快捷登录"
            @click="openLoginModal"
          >
            <User :size="15" />
            <span>工号登录</span>
          </button>

          <!-- 已登录状态：用户头像胶囊与下拉菜单 (管理后台收纳于此，普通用户无感) -->
          <div v-else ref="userMenuRef" class="user-menu-container">
            <button
              type="button"
              class="user-profile-trigger"
              :class="{ 'is-active': userMenuVisible }"
              title="个人中心与账号设置"
              @click.stop="toggleUserMenu"
            >
              <div class="user-avatar-circle">
                <span>{{ userAvatarChar }}</span>
                <span class="user-status-dot"></span>
              </div>
              <div class="user-trigger-info">
                <span class="user-trigger-name">{{ currentUserName }}</span>
                <span class="user-trigger-id mono">{{ currentUserId }}</span>
              </div>
              <ChevronDown :size="14" class="user-trigger-arrow" :class="{ 'is-flipped': userMenuVisible }" />
            </button>

            <!-- 用户下拉浮层 -->
            <Transition name="dropdown-fade">
              <div v-if="userMenuVisible" class="user-dropdown-card" @click.stop>
                <!-- 卡片头部：当前身份信息 -->
                <div class="user-dropdown-header">
                  <div class="user-card-avatar">
                    <span>{{ userAvatarChar }}</span>
                  </div>
                  <div class="user-card-meta">
                    <div class="user-card-name-row">
                      <span class="user-card-name">{{ currentUserName }}</span>
                      <span v-if="isAdmin" class="role-badge admin">管理员</span>
                      <span v-else class="role-badge user">业务用户</span>
                    </div>
                    <span class="user-card-id mono">工号: {{ currentUserId }}</span>
                  </div>
                </div>

                <!-- 权限概览条 -->
                <div class="user-grants-summary">
                  <ShieldCheck :size="14" class="text-primary" />
                  <span>享有 <strong>L0 基础公开工具</strong></span>
                  <span v-if="myGrantedToolIds.size > 0" class="granted-extra">
                    · 已授权 {{ myGrantedToolIds.size }} 项敏感特权
                  </span>
                </div>

                <div class="dropdown-divider"></div>

                <!-- 业务功能菜单列表 -->
                <div class="user-menu-list">
                  <button type="button" class="dropdown-menu-item" @click="handleMenuMyMcps">
                    <Layers :size="16" class="item-icon" />
                    <span>我添加的 MCP</span>
                    <span v-if="myMcpsList.length > 0" class="badge-count">{{ myMcpsList.length }}</span>
                  </button>

                  <button type="button" class="dropdown-menu-item" @click="handleMenuMyRequests">
                    <ListChecks :size="16" class="item-icon" />
                    <span>我的申请记录</span>
                    <span v-if="pendingRequestsCount > 0" class="badge-count">{{ pendingRequestsCount }}</span>
                  </button>

                  <button type="button" class="dropdown-menu-item" @click="handleMenuGuide">
                    <BookOpen :size="16" class="item-icon" />
                    <span>新手接入指引</span>
                  </button>

                  <!-- 管理后台（关键：仅管理员可见，普通用户无感！） -->
                  <router-link
                    v-if="isAdmin"
                    to="/admin/dashboard"
                    class="dropdown-menu-item admin-highlight-item"
                    @click="userMenuVisible = false"
                  >
                    <ShieldCheck :size="16" class="item-icon text-primary" />
                    <div class="admin-item-text">
                      <span class="admin-item-title">进入管理后台</span>
                      <span class="admin-item-sub">服务发布、审批与治理</span>
                    </div>
                  </router-link>
                </div>

                <div class="dropdown-divider"></div>

                <!-- 底部操作：切换工号与退出 -->
                <div class="user-menu-footer">
                  <button type="button" class="dropdown-action-btn" @click="openLoginModal">
                    <RefreshCw :size="14" />
                    <span>切换工号</span>
                  </button>
                  <button type="button" class="dropdown-action-btn logout-text" @click="handleLogout">
                    <LogOut :size="14" />
                    <span>退出登录</span>
                  </button>
                </div>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </header>

    <!-- ====================================================================
         2. 首屏 Hero 区域与真实活跃度指标条
         ==================================================================== -->
    <section class="portal-hero">
      <div class="hero-container">
        <div class="hero-badge">
          <Sparkles :size="14" class="text-primary" />
          <span>企业级 AI 能力自助消费平台</span>
        </div>
        <h1 class="hero-title">
          发现企业 AI 能力，一键赋能本地智能助手
        </h1>
        <p class="hero-desc">
          免登录浏览与检索，开箱即用复制对接配置；具体业务调用由 Capability Hub 统一进行安全身份鉴权。
        </p>

        <!-- 真实指标条 (真实数据驱动，无数据优雅展示空态) -->
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-icon-wrapper bg-primary-soft">
              <Layers :size="20" class="text-primary" />
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ overview?.services_count ?? '-' }}</span>
              <span class="stat-label">已上线业务服务</span>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon-wrapper bg-secondary-soft">
              <Wrench :size="20" class="text-secondary" />
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ overview?.tools_count ?? '-' }}</span>
              <span class="stat-label">可用能力工具</span>
            </div>
          </div>

          <div class="stat-card">
            <div class="stat-icon-wrapper bg-success-soft">
              <Activity :size="20" class="text-success" />
            </div>
            <div class="stat-content">
              <span class="stat-value">{{ overview?.total_calls ?? 0 }}</span>
              <span class="stat-label">平台累计真实调用</span>
            </div>
          </div>

          <!-- 近 7 日活跃趋势柱状迷你条 -->
          <div class="stat-card trend-stat-card">
            <div class="trend-header">
              <span class="stat-label">近 7 日活跃趋势</span>
              <span class="trend-total">
                {{ recent7DaysCallsTotal > 0 ? `7日: ${recent7DaysCallsTotal}次` : '暂无近7日调用' }}
              </span>
            </div>
            <div class="mini-trend-bar-chart">
              <div
                v-for="(item, idx) in trendList"
                :key="idx"
                class="mini-bar-col"
                :title="`${item.date}: 调用 ${item.calls} 次`"
              >
                <div class="mini-bar-track">
                  <div
                    class="mini-bar-fill"
                    :style="{ height: `${calculateBarHeight(item.calls)}%` }"
                  ></div>
                </div>
                <span class="mini-bar-day">{{ formatDayShort(item.date) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ====================================================================
         3. 能力发现与筛选区 (Filter Bar & Cards Grid)
         ==================================================================== -->
    <main class="portal-main">
      <div class="main-container">
        <!-- 筛选栏：分类标签 + 排序方式 -->
        <div class="discovery-filter-bar">
          <div class="category-tabs">
            <button
              v-for="cat in availableCategories"
              :key="cat"
              type="button"
              :class="['category-tab-btn', { 'is-active': selectedCategory === cat }]"
              @click="selectCategory(cat)"
            >
              {{ cat }}
            </button>
          </div>

          <div class="sort-selector">
            <span class="sort-label">排序:</span>
            <div class="sort-options">
              <button
                type="button"
                :class="['sort-opt-btn', { 'is-active': sortBy === 'popular' }]"
                @click="changeSort('popular')"
              >
                最受欢迎
              </button>
              <button
                type="button"
                :class="['sort-opt-btn', { 'is-active': sortBy === 'recent_active' }]"
                @click="changeSort('recent_active')"
              >
                最近活跃
              </button>
              <button
                type="button"
                :class="['sort-opt-btn', { 'is-active': sortBy === 'newest' }]"
                @click="changeSort('newest')"
              >
                最新上线
              </button>
            </div>
          </div>
        </div>

        <!-- 加载中骨架状态 -->
        <div v-if="loadingCapabilities" class="cards-skeleton-grid">
          <div v-for="i in 6" :key="i" class="skeleton-card">
            <div class="skeleton-header">
              <div class="skeleton-avatar"></div>
              <div class="skeleton-title-lines">
                <div class="skeleton-line w-40"></div>
                <div class="skeleton-line w-20"></div>
              </div>
            </div>
            <div class="skeleton-line w-full mt-4"></div>
            <div class="skeleton-line w-80 mt-2"></div>
            <div class="skeleton-footer mt-6">
              <div class="skeleton-line w-30"></div>
              <div class="skeleton-line w-20"></div>
            </div>
          </div>
        </div>

        <!-- 空数据状态 -->
        <div v-else-if="filteredCapabilities.length === 0" class="empty-portal-state">
          <div class="empty-icon-circle">
            <SearchX :size="32" class="text-secondary" />
          </div>
          <h3 class="type-title-md">未找到符合条件的能力服务</h3>
          <p class="type-body text-secondary mt-1">
            {{ searchKeyword ? `没有与「${searchKeyword}」匹配的结果，请尝试更换关键词` : '当前分类下暂无已发布能力' }}
          </p>
          <button
            v-if="searchKeyword || selectedCategory !== '全部'"
            type="button"
            class="reset-search-btn mt-4"
            @click="resetFilters"
          >
            重置筛选条件
          </button>
        </div>

        <!-- 正常能力卡片网格 -->
        <div v-else class="capabilities-grid">
          <div
            v-for="cap in filteredCapabilities"
            :key="cap.id"
            class="cap-card"
          >
            <!-- 卡片头部：图标、名称、状态与认证胶囊 -->
            <div class="cap-card__header">
              <div class="cap-card__avatar">
                <component :is="getCategoryIcon(cap.category)" :size="22" />
              </div>
              <div class="cap-card__title-area">
                <div class="cap-card__name-row">
                  <h3 class="cap-name" :title="cap.name">{{ cap.name }}</h3>
                  <!-- 健康状态圆点 -->
                  <span
                    class="status-indicator"
                    :class="cap.status === 'active' ? 'is-active' : 'is-degraded'"
                    :title="cap.status === 'active' ? '服务运行正常' : '服务可能降级'"
                  ></span>
                </div>
                <div class="cap-card__tags">
                  <span class="category-pill">{{ cap.category || '通用' }}</span>
                  <span class="auth-pill" :title="cap.auth_label">
                    <Shield :size="12" />
                    <span>{{ cap.auth_label || 'Hub 统一认证' }}</span>
                  </span>
                </div>
              </div>
            </div>

            <!-- 卡片主体：业务描述 (两行截断) -->
            <p class="cap-card__desc" :title="cap.description || '暂无业务描述'">
              {{ cap.description || '为本地智能助手提供高可用、标准化的业务能力集成接口。' }}
            </p>

            <!-- 卡片关键指标行 -->
            <div class="cap-card__metrics">
              <div class="metric-item">
                <Wrench :size="14" class="text-secondary" />
                <span>包含 <strong>{{ cap.tools_count }}</strong> 个工具</span>
              </div>
              <div class="metric-item">
                <Activity :size="14" class="text-secondary" />
                <span v-if="cap.call_count > 0">累计调用 <strong>{{ cap.call_count }}</strong> 次</span>
                <span v-else class="text-secondary">新上线</span>
              </div>
            </div>

            <!-- 卡片底部操作按钮 -->
            <div class="cap-card__footer">
              <button
                type="button"
                class="cap-btn detail-btn"
                @click="openDetailDrawer(cap.id)"
              >
                <span>查看详情</span>
                <ArrowRight :size="14" />
              </button>
              <button
                type="button"
                class="cap-btn access-btn"
                title="一键对接至本地 AI 助手"
                @click="handleAccessClick(cap)"
              >
                <Zap :size="14" />
                <span>一键接入</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- ====================================================================
         4. 通用接入面板弹窗 (Core Access Modal: 3 种通用 Tab + 认证说明)
         ==================================================================== -->
    <AdaptiveModal
      v-model="accessModalVisible"
      :title="selectedCap ? `接入能力: ${selectedCap.name}` : '一键接入企业 AI 能力'"
      width="880px"
    >
      <div class="access-panel">
        <!-- 顶部聚合说明横幅 -->
        <div class="aggregation-banner">
          <Info :size="18" class="banner-icon" />
          <div class="banner-content">
            <p class="banner-title">平台聚合统一端点提示</p>
            <p class="banner-text">
              只需在您的本地或网页端 AI Harness（如 Cherry Studio, Claude Desktop, Cursor 等）中添加一次平台接入地址，即可自动消费全部已发布能力，无需每个服务重复配置。
            </p>
          </div>
        </div>

        <!-- 用户身份接入状态条 (明确当前绑定工号或访客提示) -->
        <div v-if="isLoggedIn && currentUserId" class="user-binding-banner is-logged-in">
          <CheckCircle :size="16" class="text-success" />
          <span class="binding-text">
            已绑定当前登录工号: <strong>{{ currentUserName }} ({{ currentUserId }})</strong> · 专属身份 Token 已自动写入配置与请求头
          </span>
        </div>
        <div v-else class="user-binding-banner is-guest">
          <AlertCircle :size="16" class="text-warning" />
          <span class="binding-text">当前处于未登录访客模式，复制配置仅享有公开 L0 工具，无法记录敏感业务权限。</span>
          <button type="button" class="quick-login-link-btn" @click="openLoginModal">立即登录工号获取专属特权</button>
        </div>

        <!-- 3 种模式 Tab 切换 -->
        <div class="access-tabs">
          <button
            type="button"
            :class="['access-tab-btn', { 'is-active': activeAccessTab === 'form' }]"
            title="表单参数 (推荐网页端 Harness)"
            @click="activeAccessTab = 'form'"
          >
            <FileSpreadsheet :size="16" />
            <span>表单参数 (网页端)</span>
          </button>
          <button
            type="button"
            :class="['access-tab-btn', { 'is-active': activeAccessTab === 'json' }]"
            title="标准 JSON 配置 (推荐桌面端)"
            @click="activeAccessTab = 'json'"
          >
            <Code :size="16" />
            <span>标准 JSON (桌面端)</span>
          </button>
          <button
            type="button"
            :class="['access-tab-btn', { 'is-active': activeAccessTab === 'prompt' }]"
            title="自然语言安装指令 (AI 智能助手)"
            @click="activeAccessTab = 'prompt'"
          >
            <MessageSquarePlus :size="16" />
            <span>自然语言指令 (AI 助手)</span>
          </button>
        </div>

        <!-- Tab 1: 表单参数展示 -->
        <div v-if="activeAccessTab === 'form'" class="tab-pane form-pane">
          <div class="field-copy-group">
            <div class="field-row">
              <span class="field-title">服务名称 (Server Name)</span>
              <div class="field-box">
                <span class="field-val mono">{{ selectedCap ? selectedCap.name : 'AI Capability Hub' }}</span>
                <button
                  type="button"
                  class="copy-pill-btn"
                  @click="copyText(selectedCap ? selectedCap.name : 'AI Capability Hub', '服务名称')"
                >
                  <Copy :size="14" />
                  <span>复制</span>
                </button>
              </div>
            </div>

            <div class="field-row">
              <span class="field-title">传输协议 (Transport Protocol)</span>
              <div class="field-box">
                <span class="field-val mono">Streamable HTTP (MCP)</span>
                <button
                  type="button"
                  class="copy-pill-btn"
                  @click="copyText('Streamable HTTP', '传输协议')"
                >
                  <Copy :size="14" />
                  <span>复制</span>
                </button>
              </div>
            </div>

            <div class="field-row">
              <span class="field-title">服务接入地址 (Endpoint URL)</span>
              <div class="field-box highlight-box">
                <span class="field-val mono break-all">{{ currentGatewayUrl }}</span>
                <button
                  type="button"
                  class="copy-pill-btn primary"
                  @click="copyText(currentGatewayUrl, '服务接入地址')"
                >
                  <Copy :size="14" />
                  <span>一键复制地址</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Tab 2: 标准 JSON 配置 -->
        <div v-else-if="activeAccessTab === 'json'" class="tab-pane json-pane">
          <div class="code-block-header">
            <span class="code-title">mcpServers 配置片段 (指向统一 Gateway 端点)</span>
            <button
              type="button"
              class="copy-pill-btn primary"
              @click="copyText(generatedMcpJson, 'JSON 配置代码')"
            >
              <Copy :size="14" />
              <span>复制完整 JSON</span>
            </button>
          </div>
          <pre class="code-preview"><code>{{ generatedMcpJson }}</code></pre>
        </div>

        <!-- Tab 3: 自然语言指令 -->
        <div v-else-if="activeAccessTab === 'prompt'" class="tab-pane prompt-pane">
          <div class="code-block-header">
            <span class="code-title">直接将下方指令发送给具备配置能力的 AI Harness:</span>
            <button
              type="button"
              class="copy-pill-btn primary"
              @click="copyText(generatedNaturalLanguagePrompt, '自然语言指令')"
            >
              <Copy :size="14" />
              <span>复制安装指令</span>
            </button>
          </div>
          <div class="natural-prompt-box">
            {{ generatedNaturalLanguagePrompt }}
          </div>
        </div>

        <!-- 统一认证机制说明卡片 -->
        <div class="auth-notice-card">
          <div class="auth-notice-left">
            <div class="shield-circle">
              <ShieldCheck :size="20" class="text-primary" />
            </div>
            <div class="auth-notice-content">
              <div class="auth-notice-title-row">
                <span class="auth-notice-title">企业平台统一安全认证托管</span>
                <span class="auth-badge-small">{{ selectedCap?.auth_label || 'Hub 统一认证' }}</span>
              </div>
              <p class="auth-notice-desc">
                {{ selectedCap?.auth_guide || '浏览与复制配置完全免登录；当您在 AI 助手首次发起具体业务能力调用时，平台将自动引导进行企业统一身份授权，下游业务差异化鉴权由 Hub 统一换发处理。' }}
              </p>
            </div>
          </div>
          <div class="auth-notice-right">
            <button
              type="button"
              class="auth-action-btn"
              @click="handleAuthAction"
            >
              <ExternalLink :size="14" />
              <span>{{ selectedCap?.auth_entry_url ? '前往平台统一认证' : '了解授权规范' }}</span>
            </button>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="text" @click="accessModalVisible = false">关闭</MdButton>
          <MdButton variant="tonal" @click="handlePrimaryCopy">
            <Copy :size="15" />
            <span>一键复制当前配置</span>
          </MdButton>
        </div>
      </template>
    </AdaptiveModal>

    <!-- ====================================================================
         5. 能力完整详情抽屉 (Detail Drawer: 面向非开发者)
         ==================================================================== -->
    <MdDrawer
      v-model="detailDrawerVisible"
      :title="currentDetail?.name || '能力详情'"
      width="740px"
    >
      <div v-if="loadingDetail" class="detail-loading-box">
        <RefreshCw :size="24" class="is-spinning text-primary" />
        <span class="type-body text-secondary mt-2">正在加载能力详情与工具契约...</span>
      </div>

      <div v-else-if="currentDetail" class="detail-drawer-body">
        <!-- 1. 顶部概览 -->
        <div class="detail-hero-card">
          <div class="detail-title-row">
            <div class="detail-avatar">
              <component :is="getCategoryIcon(currentDetail.category)" :size="26" />
            </div>
            <div>
              <h2 class="detail-title">{{ currentDetail.name }}</h2>
              <div class="detail-tags-row mt-1">
                <span class="category-pill">{{ currentDetail.category }}</span>
                <span class="auth-pill"><Shield :size="12" /> {{ currentDetail.auth_label }}</span>
                <span class="version-pill">v{{ currentDetail.version }}</span>
              </div>
            </div>
          </div>
          <p class="detail-desc mt-3">{{ currentDetail.description || '暂无业务描述' }}</p>

          <!-- 真实调用活跃度 -->
          <div class="detail-stats-grid mt-4">
            <div class="detail-stat-box">
              <span class="stat-num">{{ currentDetail.total_calls }}</span>
              <span class="stat-sub">真实累计调用量</span>
            </div>
            <div class="detail-stat-box">
              <span class="stat-num">{{ currentDetail.recent_calls_7d }}</span>
              <span class="stat-sub">近 7 日活跃度</span>
            </div>
            <div class="detail-stat-box">
              <span class="stat-num">{{ currentDetail.tools.length }}</span>
              <span class="stat-sub">包含可用工具</span>
            </div>
          </div>
        </div>

        <!-- 2. 怎么用 (非开发者 3 步指引) -->
        <div class="usage-guide-section">
          <h3 class="section-title">
            <Compass :size="18" class="text-primary" />
            <span>三步极简接入指南</span>
          </h3>
          <div class="three-steps">
            <div class="step-card">
              <div class="step-num">1</div>
              <div class="step-body">
                <span class="step-title">一键复制配置</span>
                <span class="step-text">在下方复制标准接入地址或指令</span>
              </div>
            </div>
            <div class="step-card">
              <div class="step-num">2</div>
              <div class="step-body">
                <span class="step-title">粘贴至 AI 助手</span>
                <span class="step-text">粘贴到本地客户端或企业智能 Harness</span>
              </div>
            </div>
            <div class="step-card">
              <div class="step-num">3</div>
              <div class="step-body">
                <span class="step-title">首次统一认证</span>
                <span class="step-text">首次发起调用时，按提示完成统一授权</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 3. 适用场景与示例提问 -->
        <div v-if="currentDetail.usage_examples && currentDetail.usage_examples.length" class="examples-section">
          <h3 class="section-title">
            <MessageSquare :size="18" class="text-secondary" />
            <span>推荐提问方式与适用场景</span>
          </h3>
          <div class="examples-list">
            <div
              v-for="(example, eIdx) in currentDetail.usage_examples"
              :key="eIdx"
              class="example-pill-item"
              @click="copyText(example, '示例问法')"
            >
              <div class="example-content">
                <Quote :size="14" class="example-quote-icon" />
                <span>{{ example }}</span>
              </div>
              <button type="button" class="example-copy-btn" title="复制提示词">
                <Copy :size="13" />
              </button>
            </div>
          </div>
        </div>

        <!-- 4. 工具功能清单与精细化权限授权 -->
        <div class="tools-section">
          <div class="tools-section-header">
            <div class="tools-header-left">
              <h3 class="section-title">
                <Wrench :size="18" class="text-primary" />
                <span>包含工具功能清单 ({{ currentDetail.tools.length }})</span>
              </h3>
              <span class="type-meta text-secondary">
                基础公开功能默认对所有人开放；敏感业务操作需申请开通后方可调用
              </span>
            </div>
            <div
              v-if="currentDetail.tools.some(t => isToolSelectable(t))"
              class="tools-header-actions"
            >
              <button
                type="button"
                class="select-all-btn"
                @click="toggleSelectAllNonL0"
              >
                <CheckSquare :size="14" />
                <span>全选/反选可申请功能</span>
              </button>
            </div>
          </div>

          <div class="tools-accordion-list">
            <div
              v-for="tool in currentDetail.tools"
              :key="tool.name"
              class="tool-accordion-card"
              :class="{
                'is-selected-for-apply': selectedToolIdsForApply.has(tool.id || tool.namespace_name || tool.name),
                'is-granted': isToolGranted(tool) && !isToolL0(tool),
                'is-l0': isToolL0(tool)
              }"
            >
              <div class="tool-summary-row">
                <!-- 左侧统一对齐槽位：固定宽度 24px，消除错位 -->
                <div class="tool-col-action">
                  <!-- 可申请的敏感功能：展示复选框 -->
                  <label
                    v-if="isToolSelectable(tool)"
                    class="tool-select-checkbox-label"
                    title="勾选此功能以申请开通"
                    @click.stop
                  >
                    <input
                      type="checkbox"
                      :checked="selectedToolIdsForApply.has(tool.id || tool.namespace_name || tool.name)"
                      class="tool-checkbox"
                      @change="toggleToolSelection(tool)"
                    />
                  </label>

                  <!-- 基础公开免申请功能 (L0)：展示绿色就绪盾牌图标 -->
                  <div
                    v-else-if="isToolL0(tool)"
                    class="tool-status-icon-slot"
                    title="全员开箱即用（免申请），连接本服务后即可在 AI 助手中直接调用"
                  >
                    <CheckCircle2 :size="18" class="text-emerald-500" />
                  </div>

                  <!-- 已开通授权功能：展示已授权护盾图标 -->
                  <div
                    v-else
                    class="tool-status-icon-slot"
                    title="当前登录账号已获得此功能授权"
                  >
                    <ShieldCheck :size="18" class="text-primary" />
                  </div>
                </div>

                <!-- 工具主要业务信息区 (业务视角) -->
                <div class="tool-col-content">
                  <div class="tool-title-row">
                    <!-- 业务功能中文大标题 -->
                    <span class="tool-business-title">{{ getToolBusinessTitle(tool) }}</span>

                    <!-- 底层技术标识符 (微型次要标签，满足专业定位但不干扰普通用户) -->
                    <code class="tool-tech-slug" :title="`底层技术方法名: ${tool.name}`">{{ tool.name }}</code>

                    <!-- 通俗易懂的状态胶囊 -->
                    <span v-if="isToolL0(tool)" class="perm-pill pill-l0" title="基础公开功能，无需人工审核与额外申请">
                      <span class="pill-dot bg-emerald"></span>
                      <span>开箱即用 (免申请)</span>
                    </span>
                    <span v-else-if="isToolGranted(tool)" class="perm-pill pill-granted" title="当前工号已享有此功能调用权限">
                      <span class="pill-dot bg-primary"></span>
                      <span>已开通可用</span>
                    </span>
                    <span v-else class="perm-pill pill-need-apply" title="涉及敏感权限，勾选后点击底部按钮申请开通">
                      <span class="pill-dot bg-amber"></span>
                      <span>需申请开通</span>
                    </span>

                    <!-- 需确认标记 -->
                    <span v-if="tool.requires_confirmation" class="perm-pill pill-confirm" title="AI 调用此工具前会向您弹窗请求二次确认">
                      需确认
                    </span>
                    <span v-if="tool.requires_credentials" class="perm-pill pill-confirm" title="调用此工具需绑定个人业务凭据">
                      需个人凭据
                    </span>
                  </div>

                  <!-- 业务场景与通俗描述 -->
                  <p class="tool-business-desc">
                    {{ getToolBusinessDesc(tool) }}
                  </p>
                </div>

                <!-- 右侧折叠技术参数按钮 (开发者视角，弱化收起) -->
                <div class="tool-col-toggle">
                  <button
                    type="button"
                    class="schema-toggle-btn"
                    :title="expandedTools.has(tool.name) ? '收起技术参数' : '查看该工具的标准 Input JSON Schema'"
                    @click="toggleToolSchema(tool.name)"
                  >
                    <span>{{ expandedTools.has(tool.name) ? '收起参数' : '技术参数' }}</span>
                    <ChevronDown
                      :size="13"
                      :class="{ 'rotate-180': expandedTools.has(tool.name) }"
                    />
                  </button>
                </div>
              </div>

              <!-- 折叠的技术参数定义 (开发者/技术视角) -->
              <div v-show="expandedTools.has(tool.name)" class="tool-schema-collapse">
                <div class="schema-code-header">
                  <span class="schema-code-label">方法名: <code>{{ tool.name }}</code> · 风险等级: {{ tool.risk_level }}</span>
                  <button
                    type="button"
                    class="copy-text-action"
                    @click="copyText(JSON.stringify(tool.input_schema, null, 2), 'Input Schema')"
                  >
                    <Copy :size="12" />
                    <span>复制 Schema</span>
                  </button>
                </div>
                <pre class="schema-code-block"><code>{{ JSON.stringify(tool.input_schema, null, 2) }}</code></pre>
              </div>
            </div>
          </div>
        </div>

        <!-- 抽屉底部快捷接入栏与申请按钮 (布局强化，消除换行与挤压) -->
        <div class="detail-drawer-footer-card">
          <div class="drawer-footer-text">
            <span class="footer-title">
              {{ selectedToolIdsForApply.size > 0 ? `已勾选 ${selectedToolIdsForApply.size} 项需开通的功能` : '一键接入本服务' }}
            </span>
            <span class="footer-hint">
              {{ selectedToolIdsForApply.size > 0 ? '提交后由管理员在线审核，通过后本地客户端下次对话自动点亮' : '复制配置到 AI 客户端，默认享有所有免申请的基础公开能力' }}
            </span>
          </div>
          <div class="drawer-footer-actions-group">
            <button
              v-if="selectedToolIdsForApply.size > 0"
              type="button"
              class="action-btn apply-perm-btn"
              @click="openApplyModal"
            >
              <LockOpen :size="15" />
              <span>申请开通所选功能 ({{ selectedToolIdsForApply.size }})</span>
            </button>
            <button
              type="button"
              class="action-btn access-highlight-btn"
              @click="handleAccessClick(currentDetail || undefined)"
            >
              <Zap :size="15" />
              <span>一键接入本地</span>
            </button>
          </div>
        </div>
      </div>
    </MdDrawer>

    <!-- ====================================================================
         6. 新手快速上手指南模态框
         ==================================================================== -->
    <AdaptiveModal
      v-model="guideModalVisible"
      title="非开发者 3 步快速上手指南"
      width="640px"
    >
      <div class="guide-modal-content">
        <div class="guide-step-row">
          <div class="guide-step-badge">1</div>
          <div class="guide-step-detail">
            <h4 class="guide-step-heading">挑选所需业务能力</h4>
            <p class="guide-step-body">
              通过本门户顶部的全局搜索或分类筛选，找到契合您当前业务场景的能力卡片（如知识库检索、消息推送或业务数据分析）。
            </p>
          </div>
        </div>

        <div class="guide-step-row">
          <div class="guide-step-badge">2</div>
          <div class="guide-step-detail">
            <h4 class="guide-step-heading">复制一键接入配置</h4>
            <p class="guide-step-body">
              点击卡片底部的「一键接入」按钮。如果您使用支持自然语言指令的 AI Harness，复制 Tab 3 的指令直接发给它；如果是桌面端客户端，复制 Tab 2 的标准 JSON 粘贴到 mcpServers 即可。
            </p>
          </div>
        </div>

        <div class="guide-step-row">
          <div class="guide-step-badge">3</div>
          <div class="guide-step-detail">
            <h4 class="guide-step-heading">在对话中自然使用</h4>
            <p class="guide-step-body">
              配置完成后，直接向您的本地 AI 助手提问（如“帮我统计今日投资组合情况”）。AI 助手将自动调用 Capability Hub，首次调用时会按需触发企业统一身份授权。
            </p>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="tonal" @click="guideModalVisible = false">我已了解，开始体验</MdButton>
        </div>
      </template>
    </AdaptiveModal>

    <!-- ====================================================================
         7. 工具功能权限申请弹窗
         ==================================================================== -->
    <AdaptiveModal
      v-model="applyModalVisible"
      title="申请开通工具功能权限"
      width="560px"
    >
      <div class="apply-modal-content">
        <div class="apply-summary-banner">
          <Info :size="18" class="banner-icon" />
          <div class="banner-text">
            您正在为 <strong>{{ currentDetail?.name }}</strong> 申请开通以下功能。审批通过后，本地客户端将自动无缝感知并解锁这些功能，无需重新配置接入地址。
          </div>
        </div>

        <div class="apply-form-section mt-4">
          <label class="form-label font-medium">拟开通功能列表 ({{ selectedToolIdsForApply.size }} 项)</label>
          <div class="selected-tools-pill-group">
            <span
              v-for="item in getSelectedToolsForApplySummary()"
              :key="item.id"
              class="tool-apply-pill"
            >
              <span class="tool-pill-name font-medium">{{ item.name }}</span>
              <code v-if="item.techName && item.techName !== item.name" class="tool-pill-tech">{{ item.techName }}</code>
              <span class="tool-pill-risk" :class="`risk-${item.risk.toLowerCase()}`">{{ item.risk }}</span>
            </span>
          </div>
        </div>

        <div class="apply-form-section mt-3">
          <label class="form-label font-medium">申请人工号与姓名</label>
          <div class="user-row-grid">
            <input
              v-model="currentUserId"
              type="text"
              placeholder="工号 (如 U10086)"
              class="form-input mono"
              @change="persistUserIdentity"
            />
            <input
              v-model="currentUserName"
              type="text"
              placeholder="姓名"
              class="form-input"
              @change="persistUserIdentity"
            />
          </div>
        </div>

        <!-- 业务凭据要求与动态输入表单 (仅当本次勾选的工具中包含需凭据工具时展示) -->
        <div v-if="selectedRequiresCredentials" class="apply-form-section mt-3 credential-binding-section">
          <div class="credential-section-header flex items-center gap-1">
            <Key :size="16" class="text-primary" />
            <label class="form-label font-medium mb-0">个人业务凭据绑定</label>
          </div>
          <div class="credential-desc-tip text-secondary text-xs mt-1">
            {{ currentDetail.credential_schema.instructions || '此服务要求验证个人业务账号，所有已获批工具将共用此绑定。' }}
          </div>

          <!-- 已绑定提示与复用 -->
          <div v-if="currentServiceExistingBinding" class="credential-bound-card mt-2 p-2 rounded flex items-center gap-2">
            <CheckCircle2 :size="16" class="text-success" />
            <div class="bound-card-text text-xs">
              已绑定账号: <strong>{{ currentServiceExistingBinding.credential_summary?.username || '已保存凭据' }}</strong>
              <span class="text-secondary">（本次申请将自动复用该账号）</span>
            </div>
            <button type="button" class="btn-text-link text-xs ml-auto" @click="showCustomCredInApply = !showCustomCredInApply">
              {{ showCustomCredInApply ? '收起修改' : '修改账号密码' }}
            </button>
          </div>

          <!-- 动态字段输入 -->
          <div v-if="!currentServiceExistingBinding || showCustomCredInApply" class="credential-inputs-grid mt-2 grid gap-2">
            <div
              v-for="field in currentDetail.credential_schema.fields"
              :key="field.field_name"
              class="credential-input-item"
            >
              <label class="field-label-text text-xs font-medium text-secondary block mb-1">
                {{ field.label }}
                <span v-if="field.required" class="text-error">*</span>
              </label>
              <input
                v-model="applyCredentialForm[field.field_name]"
                :type="field.field_type === 'password' ? 'password' : 'text'"
                :placeholder="field.placeholder || field.description || `请输入${field.label}`"
                class="form-input"
                :class="{ mono: field.field_type === 'password' }"
              />
            </div>
          </div>
        </div>

        <div class="apply-form-section mt-3">
          <label class="form-label font-medium">
            申请原因 / 业务场景说明 <span class="text-error">*</span>
          </label>
          <textarea
            v-model="applyReason"
            rows="3"
            placeholder="请简述该工具的日常工作场景及申请理由（如：用于日常组合分析与风控提醒推送）"
            class="form-textarea"
          ></textarea>
        </div>
      </div>
      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="text" @click="applyModalVisible = false">取消</MdButton>
          <MdButton
            variant="tonal"
            :disabled="submittingApply || !applyReason.trim()"
            @click="submitPermissionApplication"
          >
            <span v-if="submittingApply">正在提交...</span>
            <span v-else>确认提交申请</span>
          </MdButton>
        </div>
      </template>
    </AdaptiveModal>

    <!-- ====================================================================
         8. 我的权限申请记录抽屉
         ==================================================================== -->
    <MdDrawer
      v-model="myRequestsDrawerVisible"
      title="我的功能权限申请记录"
      width="600px"
    >
      <div v-if="loadingMyRequests" class="detail-loading-box">
        <RefreshCw :size="24" class="is-spinning text-primary" />
        <span class="type-body text-secondary mt-2">正在加载申请记录...</span>
      </div>
      <div v-else-if="!myRequests.length" class="empty-requests-box">
        <ListChecks :size="48" class="text-secondary opacity-40" />
        <p class="mt-3 font-medium text-secondary">暂无权限申请记录</p>
        <p class="text-sm text-secondary opacity-70 mt-1">在能力详情抽屉勾选非 L0 工具即可提交开通申请</p>
      </div>
      <div v-else class="my-requests-list">
        <div
          v-for="req in myRequests"
          :key="req.id"
          class="req-record-card"
        >
          <div class="req-card-header">
            <div class="req-svc-title">
              <span class="font-medium text-on-surface">{{ req.service_name || req.service_id }}</span>
              <span class="req-id-tag mono">{{ req.id }}</span>
            </div>
            <div class="req-status-pill" :class="`status-${req.status}`">
              <span v-if="req.status === 'approved'">🟢 已通过</span>
              <span v-else-if="req.status === 'rejected'">🔴 已驳回</span>
              <span v-else>🟡 待审批</span>
            </div>
          </div>

          <div class="req-tools-box mt-2">
            <span class="req-tools-label text-secondary">申请功能:</span>
            <span
              v-for="tName in req.tool_names"
              :key="tName"
              class="req-tool-tag"
            >
              {{ tName }}
            </span>
          </div>

          <p class="req-reason-text mt-2 text-sm text-secondary">
            <strong>申请理由:</strong> {{ req.reason || '无说明' }}
          </p>

          <div v-if="req.comment" class="req-comment-box mt-2">
            <span class="text-xs font-medium">审批批注 ({{ req.reviewed_by || '管理员' }}):</span>
            <p class="text-xs text-secondary mt-0.5">{{ req.comment }}</p>
          </div>

          <div class="req-time-row mt-2 text-xs text-secondary">
            <span>提交时间: {{ req.created_at ? req.created_at.slice(0, 19).replace('T', ' ') : '-' }}</span>
            <span v-if="req.reviewed_at">审批时间: {{ req.reviewed_at.slice(0, 19).replace('T', ' ') }}</span>
          </div>
        </div>
      </div>
    </MdDrawer>

    <!-- ====================================================================
         8.5 我添加的 MCP 综合管理抽屉 (ADR-011)
         ==================================================================== -->
    <MdDrawer
      v-model="myMcpsDrawerVisible"
      title="我添加的 MCP 能力"
      width="640px"
    >
      <div v-if="loadingMyMcps" class="detail-loading-box">
        <RefreshCw :size="24" class="is-spinning text-primary" />
        <span class="type-body text-secondary mt-2">正在加载 MCP 资产...</span>
      </div>
      <div v-else-if="!myMcpsList.length" class="empty-requests-box">
        <Layers :size="48" class="text-secondary opacity-40" />
        <p class="mt-3 font-medium text-secondary">暂未添加任何 MCP 服务</p>
        <p class="text-sm text-secondary opacity-70 mt-1">在能力列表中点击“申请开通”或“一键接入”即可添加</p>
      </div>
      <div v-else class="my-mcps-container p-4 space-y-4">
        <div
          v-for="item in myMcpsList"
          :key="item.service_id"
          class="my-mcp-item-card border rounded-lg p-4 bg-surface"
        >
          <div class="flex items-center justify-between">
            <div>
              <span class="text-base font-semibold text-on-surface">{{ item.service_name }}</span>
              <span class="ml-2 text-xs mono px-2 py-0.5 rounded bg-surface-container">{{ item.service_id }}</span>
            </div>
            <!-- 凭据状态与审批状态胶囊 -->
            <span
              class="px-2.5 py-1 text-xs rounded-full font-medium"
              :class="getMyMcpStatusClass(item)"
            >
              {{ getMyMcpStatusLabel(item) }}
            </span>
          </div>

          <!-- 已获批工具 -->
          <div class="mt-3 text-xs">
            <span class="text-secondary font-medium">已获批工具:</span>
            <div v-if="item.approved_tools && item.approved_tools.length" class="flex flex-wrap gap-1.5 mt-1">
              <span
                v-for="tool in item.approved_tools"
                :key="tool"
                class="px-2 py-0.5 bg-success-container text-on-success-container rounded text-xs"
              >
                {{ tool }}
              </span>
            </div>
            <span v-else class="text-secondary ml-1">暂无获批工具</span>
          </div>

          <!-- 待审批工具 -->
          <div v-if="item.pending_tools && item.pending_tools.length" class="mt-2 text-xs">
            <span class="text-secondary font-medium">待审批工具:</span>
            <div class="flex flex-wrap gap-1.5 mt-1">
              <span
                v-for="tool in item.pending_tools"
                :key="tool"
                class="px-2 py-0.5 bg-warning-container text-on-warning-container rounded text-xs"
              >
                {{ tool }}
              </span>
            </div>
          </div>

          <!-- 个人业务凭据状态与改密/解绑操作区 -->
          <div v-if="item.requires_credentials" class="mt-3 pt-3 border-t border-dashed flex items-center justify-between text-xs">
            <div class="flex items-center gap-1.5 text-secondary">
              <Key :size="14" class="text-primary" />
              <span>
                业务账号: <strong class="text-on-surface">{{ item.credential_summary?.username || '未配置' }}</strong>
                <span v-if="item.downstream_status === 'unavailable' || item.service_status === 'degraded' || item.service_status === 'inactive'" class="ml-1 text-error">
                  （下游不可用{{ item.downstream_error ? `: ${item.downstream_error}` : '' }}）
                </span>
                <span v-else-if="item.credential_status === 'verified'" class="ml-1 text-success">（已验证）</span>
                <span v-else-if="item.credential_status === 'saved'" class="ml-1 text-primary">（已保存，待调用验证）</span>
                <span v-else-if="item.credential_status === 'invalid'" class="ml-1 text-error">（登录失效，请更新密码）</span>
                <span v-else-if="item.credential_status === 'unbound'" class="ml-1 text-error">（已解绑，调用已阻断）</span>
                <span v-else class="ml-1 text-warning">（未配置有效凭据）</span>
              </span>
            </div>
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="text-primary hover:underline text-xs"
                @click="openEditBindingDialog(item)"
              >
                修改密码/账号
              </button>
              <button
                v-if="item.credential_status === 'saved' || item.credential_status === 'verified' || item.credential_status === 'invalid'"
                type="button"
                class="text-error hover:underline text-xs"
                @click="handleUnbindService(item)"
              >
                解绑
              </button>
            </div>
          </div>
          <div v-else-if="item.downstream_status === 'unavailable' || item.service_status === 'degraded' || item.service_status === 'inactive'" class="mt-3 pt-3 border-t border-dashed text-xs text-error">
            下游不可用{{ item.downstream_error ? `：${item.downstream_error}` : '：服务暂不可达或已停用' }}
          </div>
        </div>
      </div>
    </MdDrawer>

    <!-- 改密弹窗 -->
    <AdaptiveModal
      v-model="editBindingModalVisible"
      title="更新个人业务凭据"
      description="更新业务账号密码。新凭据将立即加密保存，原会话立即失效以确保安全。"
      width="460px"
    >
      <div v-if="editingMcpItem" class="edit-binding-content space-y-3">
        <div class="text-xs text-secondary mb-2">
          正在为服务 <strong>{{ editingMcpItem.service_name }}</strong> 更新业务账号凭据。
        </div>
        <div class="form-item">
          <label class="form-label font-medium text-xs">业务用户名 / 账号</label>
          <input
            v-model="editBindingForm.username"
            type="text"
            placeholder="请输入业务用户名"
            class="form-input text-xs"
          />
        </div>
        <div class="form-item mt-2">
          <label class="form-label font-medium text-xs">新密码</label>
          <input
            v-model="editBindingForm.password"
            type="password"
            placeholder="请输入新密码（留空则不修改密码）"
            class="form-input text-xs mono"
          />
        </div>
      </div>
      <template #footer>
        <div class="modal-footer-actions">
          <MdButton variant="text" @click="editBindingModalVisible = false">取消</MdButton>
          <MdButton
            variant="tonal"
            :disabled="submittingEditBinding || !editBindingForm.username.trim()"
            @click="submitEditBinding"
          >
            <span v-if="submittingEditBinding">正在保存...</span>
            <span v-else>确认保存</span>
          </MdButton>
        </div>
      </template>
    </AdaptiveModal>

    <!-- ====================================================================
         9. 工号快捷登录 / 身份接入模态框
         ==================================================================== -->
    <AdaptiveModal
      v-model="loginModalVisible"
      title="工号快捷登录"
      description="绑定企业工号以换发专属 MCP 访问凭据，开启工具申请与调用权限"
      width="440px"
    >
      <div class="login-modal-content">
        <!-- 核心工号表单 -->
        <div class="manual-login-form">
          <div class="form-item">
            <label class="form-label font-medium">企业工号 <span class="text-error">*</span></label>
            <input
              v-model="loginForm.userId"
              type="text"
              placeholder="请输入企业工号 (如 U10086, dev-user)"
              class="form-input mono"
              @keyup.enter="handleConfirmLogin"
            />
          </div>
          <div class="form-item mt-3">
            <label class="form-label font-medium">员工姓名 (选填)</label>
            <input
              v-model="loginForm.userName"
              type="text"
              placeholder="请输入姓名 (如 张三)"
              class="form-input"
              @keyup.enter="handleConfirmLogin"
            />
          </div>
        </div>

        <!-- 联调演示快捷标签 -->
        <div class="demo-quick-section mt-4">
          <span class="demo-quick-title">联调身份快捷填入:</span>
          <div class="demo-quick-tags">
            <button
              type="button"
              class="demo-tag-btn"
              :class="{ 'is-active': loginForm.userId === 'dev-user' }"
              @click="quickFillIdentity('dev-user', '张三', 'user')"
            >
              <User :size="12" />
              <span>张三 (业务员工)</span>
            </button>
            <button
              type="button"
              class="demo-tag-btn"
              :class="{ 'is-active': loginForm.userId === 'risk-01' }"
              @click="quickFillIdentity('risk-01', '李四', 'user')"
            >
              <User :size="12" />
              <span>李四 (风控分析)</span>
            </button>
            <button
              type="button"
              class="demo-tag-btn admin"
              :class="{ 'is-active': loginForm.userId === 'admin' }"
              @click="quickFillIdentity('admin', '系统管理员', 'admin')"
            >
              <ShieldCheck :size="12" />
              <span>管理员 (平台审批)</span>
            </button>
          </div>
        </div>
      </div>

      <template #actions>
        <div class="modal-footer-actions">
          <MdButton variant="text" @click="loginModalVisible = false">取消</MdButton>
          <MdButton
            variant="tonal"
            :disabled="!loginForm.userId.trim()"
            @click="handleConfirmLogin"
          >
            确认登录并接入
          </MdButton>
        </div>
      </template>
    </AdaptiveModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  Cpu,
  Search,
  X,
  Zap,
  BookOpen,
  Sun,
  Moon,
  ShieldCheck,
  Sparkles,
  Layers,
  Wrench,
  Activity,
  SearchX,
  ArrowRight,
  Shield,
  Info,
  FileSpreadsheet,
  Code,
  MessageSquarePlus,
  Copy,
  ExternalLink,
  Compass,
  MessageSquare,
  Quote,
  ChevronDown,
  RefreshCw,
  FolderKanban,
  FileText,
  BarChart3,
  Bot,
  User,
  ListChecks,
  CheckSquare,
  LockOpen,
  CheckCircle,
  CheckCircle2,
  AlertCircle,
  LogOut,
  Key
} from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'
import { useToast } from '@/composables/useToast'
import { MdButton, MdDrawer, AdaptiveModal, McpLogo } from '@/components/m3'
import {
  portalLogin,
  getPortalOverview,
  getPortalCapabilities,
  getPortalCapabilityDetail,
  getPortalMyConfig,
  getPortalMyGrants,
  createPortalPermissionRequest,
  getPortalMyRequests,
  getPortalMyMcps,
  updatePortalServiceBinding,
  unbindPortalServiceBinding,
  type PortalOverview,
  type PortalCapabilityCard,
  type PortalCapabilityDetail,
  type PortalTrendItem,
  type PermissionRequest,
  type UserClientConfig,
  type UserMcpDetail,
} from '@/api/portal'
import {
  buildPermissionRequestPayload,
  getMyMcpStatusClass,
  getMyMcpStatusLabel,
  selectedToolsRequireCredentials,
  validateCredentialFormForSelectedTools,
} from './mcpStatus'

const themeStore = useThemeStore()
const toast = useToast()

const isMac = computed(() => {
  return typeof navigator !== 'undefined' && /macintosh|mac os x/i.test(navigator.userAgent)
})

// 1. 概览与真实统计
const overview = ref<PortalOverview | null>(null)
const loadingOverview = ref(false)

// 2. 能力列表与搜索过滤
const capabilities = ref<PortalCapabilityCard[]>([])
const loadingCapabilities = ref(false)
const searchKeyword = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)
const selectedCategory = ref('全部')
const sortBy = ref<'popular' | 'recent_active' | 'newest'>('popular')

// 3. 接入配置模态框状态
const accessModalVisible = ref(false)
const selectedCap = ref<PortalCapabilityCard | null>(null)
const activeAccessTab = ref<'form' | 'json' | 'prompt'>('form')

// 4. 详情抽屉状态
const detailDrawerVisible = ref(false)
const loadingDetail = ref(false)
const currentDetail = ref<PortalCapabilityDetail | null>(null)
const expandedTools = ref<Set<string>>(new Set())

// 5. 新手指南模态框
const guideModalVisible = ref(false)

// 6. 用户身份与认证状态体系 (严格以 localStorage portal_user_id 为准，未设置时严格为未登录)
const savedUserId = localStorage.getItem('portal_user_id')
const savedUserName = localStorage.getItem('portal_user_name')
const savedUserRole = localStorage.getItem('portal_user_role')

// 只有当 savedUserId 存在且非空时才为登录状态
const isLoggedIn = ref(Boolean(savedUserId && savedUserId.trim() !== ''))
const currentUserId = ref(isLoggedIn.value ? savedUserId!.trim() : '')
const currentUserName = ref(isLoggedIn.value ? (savedUserName?.trim() || savedUserId!.trim()) : '未登录')
const currentUserRole = ref(isLoggedIn.value ? (savedUserRole?.trim() || 'user') : 'guest')

// 一键接入待流转目标（未登录点击接入时暂存目标能力，登录后自动直达接入）
const pendingAccessCap = ref<PortalCapabilityCard | null | undefined>(undefined)

// 用户下拉菜单状态与节点引用
const userMenuVisible = ref(false)
const userMenuRef = ref<HTMLElement | null>(null)

// 快捷工号登录/切换身份弹窗状态
const loginModalVisible = ref(false)
const loginForm = ref({
  userId: currentUserId.value || 'dev-user',
  userName: currentUserName.value === '未登录' ? '张三' : currentUserName.value,
  role: currentUserRole.value === 'guest' ? 'user' : currentUserRole.value
})

// 头像文字
const userAvatarChar = computed(() => {
  if (currentUserName.value && currentUserName.value.trim()) {
    return currentUserName.value.trim().slice(0, 1).toUpperCase()
  }
  if (currentUserId.value && currentUserId.value.trim()) {
    return currentUserId.value.trim().slice(0, 1).toUpperCase()
  }
  return 'U'
})

// 关键权限判定：仅管理员可见管理后台，普通业务用户完全无感
const isAdmin = computed(() => {
  if (!isLoggedIn.value) return false
  const uid = currentUserId.value.toLowerCase().trim()
  const role = currentUserRole.value.toLowerCase().trim()
  return (
    role === 'admin' ||
    uid === 'admin' ||
    uid.startsWith('admin_') ||
    uid.startsWith('admin-') ||
    Boolean(localStorage.getItem('hub_admin_api_key'))
  )
})

const userClientConfig = ref<UserClientConfig | null>(null)
const myGrantedToolIds = ref<Set<string>>(new Set())

// 7. 功能权限申请状态
const selectedToolIdsForApply = ref<Set<string>>(new Set())
const applyModalVisible = ref(false)
const applyReason = ref('')
const submittingApply = ref(false)

// 8. 用户申请记录抽屉
const myRequestsDrawerVisible = ref(false)
const myRequests = ref<PermissionRequest[]>([])
const loadingMyRequests = ref(false)

// 待审批申请数量派生：从实际审批状态派生 pendingRequestsCount
const pendingRequestsCount = computed(() => {
  if (!myRequests.value || myRequests.value.length === 0) return 0
  return myRequests.value.filter(r => r.status === 'pending').length
})

// 8.5 我添加的 MCP 与个人凭据绑定状态
const myMcpsDrawerVisible = ref(false)
const loadingMyMcps = ref(false)
const myMcpsList = ref<UserMcpDetail[]>([])
const applyCredentialForm = ref<Record<string, string>>({})
const showCustomCredInApply = ref(false)
const editBindingModalVisible = ref(false)
const editingMcpItem = ref<UserMcpDetail | null>(null)
const editBindingForm = ref({ username: '', password: '' })
const submittingEditBinding = ref(false)

// 当前打开能力详情时，是否已有已绑定的有效业务凭据
const currentServiceExistingBinding = computed(() => {
  if (!currentDetail.value || !myMcpsList.value.length) return null
  return (
    myMcpsList.value.find(
      m =>
        m.service_id === currentDetail.value?.id &&
        (m.credential_status === 'saved' || m.credential_status === 'verified' || m.credential_status === 'active')
    ) || null
  )
})

// 本次勾选申请的工具是否需要个人业务凭据（按具体工具判定，而非整个服务）
const selectedRequiresCredentials = computed(() => {
  return selectedToolsRequireCredentials(currentDetail.value, selectedToolIdsForApply.value)
})

// 获取当前浏览器访问的主机统一 Gateway 地址
const currentGatewayUrl = computed(() => {
  if (userClientConfig.value?.gateway_url) {
    return userClientConfig.value.gateway_url
  }
  if (currentDetail.value?.gateway_url) {
    return currentDetail.value.gateway_url
  }
  if (typeof window !== 'undefined') {
    return `${window.location.origin}/mcp`
  }
  return 'http://127.0.0.1:8080/mcp'
})

// 带身份凭据的客户端连接地址（双保险：url query + headers 均带 Token）
const currentGatewayUrlWithToken = computed(() => {
  const base = currentGatewayUrl.value
  if (userClientConfig.value?.token) {
    return `${base}?token=${userClientConfig.value.token}`
  }
  return base
})

// 近 7 日调用趋势列表与总数
const trendList = computed<PortalTrendItem[]>(() => {
  return overview.value?.daily_trends || []
})

const recent7DaysCallsTotal = computed(() => {
  return trendList.value.reduce((acc, curr) => acc + curr.calls, 0)
})

// 动态提取已有分类标签
const availableCategories = computed(() => {
  const cats = new Set<string>(['全部'])
  capabilities.value.forEach(c => {
    if (c.category) {
      cats.add(c.category)
    }
  })
  return Array.from(cats)
})

// 前端即时过滤
const filteredCapabilities = computed(() => {
  return capabilities.value.filter(c => {
    // 1. 分类匹配
    if (selectedCategory.value !== '全部' && c.category !== selectedCategory.value) {
      return false
    }
    // 2. 关键词匹配 (支持拼音/英文/中文服务名与描述)
    if (searchKeyword.value.trim()) {
      const kw = searchKeyword.value.trim().toLowerCase()
      const matchName = c.name.toLowerCase().includes(kw)
      const matchDesc = (c.description || '').toLowerCase().includes(kw)
      const matchCat = (c.category || '').toLowerCase().includes(kw)
      if (!matchName && !matchDesc && !matchCat) {
        return false
      }
    }
    return true
  })
})

// 生成带专属身份认证 Token 的 mcpServers JSON 配置（标准规范：仅在请求头携带令牌，避免 URL 重复携带进入访问日志）
const generatedMcpJson = computed(() => {
  const token = userClientConfig.value?.token || ''
  const url = currentGatewayUrl.value
  const serverKey = selectedCap.value ? selectedCap.value.id : 'ai-capability-hub'
  const config = {
    mcpServers: {
      [serverKey]: {
        transport: 'streamable-http',
        url: url,
        headers: token
          ? {
              Authorization: `Bearer ${token}`,
            }
          : undefined,
      },
    },
  }
  return JSON.stringify(config, null, 2)
})

// 生成给 AI 助手的自然语言接入指令
const generatedNaturalLanguagePrompt = computed(() => {
  const name = selectedCap.value ? selectedCap.value.name : 'AI Capability Hub'
  const desc = selectedCap.value?.description ? `主要功能：${selectedCap.value.description}` : '提供企业统一业务能力'
  const token = userClientConfig.value?.token
  const authLine = token ? `- 鉴权请求头: Authorization: Bearer ${token}\n` : ''
  const identityDesc = isLoggedIn.value && currentUserId.value
    ? `（已绑定工号 ${currentUserId.value} 专属凭证，默认享有 L0 基础公开工具）`
    : '（公共访客模式接入，享有 L0 基础公开工具；可在 MCP中心 登录工号以开通敏感业务权限）'
  return `请帮我添加并配置以下 MCP 服务：
- 服务名称: ${name}
- 传输协议: Streamable HTTP
- 端点地址: ${currentGatewayUrl.value}
${authLine}- 说明: ${desc} ${identityDesc}
配置完成后请重新加载 MCP 工具列表。`
})

// 分类图标映射
function getCategoryIcon(cat?: string) {
  if (!cat) return Bot
  if (cat.includes('知识') || cat.includes('文档')) return FileText
  if (cat.includes('数据') || cat.includes('分析')) return BarChart3
  if (cat.includes('业务') || cat.includes('协作')) return FolderKanban
  return Bot
}

function calculateBarHeight(calls: number): number {
  if (!recent7DaysCallsTotal.value || recent7DaysCallsTotal.value === 0) return 4
  const max = Math.max(...trendList.value.map(t => t.calls), 1)
  const percent = Math.round((calls / max) * 100)
  return Math.max(percent, 8)
}

function formatDayShort(dateStr: string): string {
  if (!dateStr) return '-'
  const parts = dateStr.split('-')
  return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : dateStr
}

async function loadOverview() {
  loadingOverview.value = true
  try {
    overview.value = await getPortalOverview()
  } catch (err: unknown) {
    console.error('加载概览统计失败:', err)
  } finally {
    loadingOverview.value = false
  }
}

async function loadCapabilities() {
  loadingCapabilities.value = true
  try {
    capabilities.value = await getPortalCapabilities({
      category: selectedCategory.value !== '全部' ? selectedCategory.value : undefined,
      sort_by: sortBy.value,
    })
  } catch (err: unknown) {
    console.error('加载能力列表失败:', err)
  } finally {
    loadingCapabilities.value = false
  }
}

function handleSearchInput() {
  // 本地即时计算过滤，同时支持防抖拉取后端检索（当前采用前端即时响应提升业务流畅感）
}

function clearSearch() {
  searchKeyword.value = ''
}

function selectCategory(cat: string) {
  selectedCategory.value = cat
}

function changeSort(sort: 'popular' | 'recent_active' | 'newest') {
  sortBy.value = sort
  loadCapabilities()
}

function resetFilters() {
  searchKeyword.value = ''
  selectedCategory.value = '全部'
  sortBy.value = 'popular'
  loadCapabilities()
}

function openGlobalAccessModal() {
  selectedCap.value = null
  activeAccessTab.value = 'form'
  accessModalVisible.value = true
}

function openAccessModal(cap: PortalCapabilityCard) {
  selectedCap.value = cap
  activeAccessTab.value = 'form'
  accessModalVisible.value = true
}

async function openDetailDrawer(id: string) {
  detailDrawerVisible.value = true
  loadingDetail.value = true
  expandedTools.value.clear()
  selectedToolIdsForApply.value.clear()
  applyCredentialForm.value = {}
  showCustomCredInApply.value = false
  try {
    currentDetail.value = await getPortalCapabilityDetail(id)
    await Promise.all([loadUserConfigAndGrants(), loadMyMcps()])
  } catch (err: unknown) {
    toast.error('获取能力详情失败')
    detailDrawerVisible.value = false
  } finally {
    loadingDetail.value = false
  }
}

function persistUserIdentity() {
  localStorage.setItem('portal_user_id', currentUserId.value)
  localStorage.setItem('portal_user_name', currentUserName.value)
  loadUserConfigAndGrants()
}

function openLoginModal() {
  userMenuVisible.value = false
  loginForm.value = {
    userId: currentUserId.value || 'dev-user',
    userName: currentUserName.value === '未登录' ? '张三' : currentUserName.value,
    role: currentUserRole.value === 'guest' ? 'user' : currentUserRole.value
  }
  loginModalVisible.value = true
}

function handleAccessClick(cap?: PortalCapabilityCard | PortalCapabilityDetail) {
  if (!isLoggedIn.value) {
    pendingAccessCap.value = (cap as PortalCapabilityCard) || null
    toast.info('一键接入需绑定您的企业工号以换发专属凭证，请先完成快捷登录')
    openLoginModal()
    return
  }
  if (cap) {
    openAccessModal(cap as PortalCapabilityCard)
  } else {
    openGlobalAccessModal()
  }
}

function quickFillIdentity(id: string, name: string, role: string) {
  loginForm.value.userId = id
  loginForm.value.userName = name
  loginForm.value.role = role
}

async function handleConfirmLogin() {
  const uid = loginForm.value.userId.trim()
  const uname = loginForm.value.userName.trim() || uid
  const urole = loginForm.value.role || (uid.toLowerCase().includes('admin') ? 'admin' : 'user')

  if (!uid) {
    toast.error('请输入工号')
    return
  }

  try {
    const authRes = await portalLogin(uid, uname)
    if (authRes && authRes.token) {
      localStorage.setItem('portal_token', authRes.token)
    }
  } catch (err) {
    console.warn('登录认证服务端换发令牌失败:', err)
  }

  currentUserId.value = uid
  currentUserName.value = uname
  currentUserRole.value = urole
  isLoggedIn.value = true

  localStorage.setItem('portal_user_id', uid)
  localStorage.setItem('portal_user_name', uname)
  localStorage.setItem('portal_user_role', urole)

  // 若以管理员身份登录，顺畅打通控制台 API Key 存储
  if (urole === 'admin' || uid.toLowerCase() === 'admin') {
    if (!localStorage.getItem('hub_admin_api_key')) {
      localStorage.setItem('hub_admin_api_key', 'dev-admin-key')
      localStorage.setItem('hub_admin_user', uid)
    }
  }

  loginModalVisible.value = false
  toast.success(`已登录工号: ${uname} (${uid})`)

  await loadUserConfigAndGrants()

  // 若之前是由于未登录点击一键接入触发的登录，登录成功后自动打开接入弹窗
  if (pendingAccessCap.value !== undefined) {
    const target = pendingAccessCap.value
    pendingAccessCap.value = undefined
    if (target) {
      openAccessModal(target)
    } else {
      openGlobalAccessModal()
    }
  }
}

function handleLogout() {
  userMenuVisible.value = false
  isLoggedIn.value = false
  currentUserId.value = ''
  currentUserName.value = '未登录'
  currentUserRole.value = 'guest'
  localStorage.removeItem('portal_user_id')
  localStorage.removeItem('portal_user_name')
  localStorage.removeItem('portal_user_role')
  localStorage.removeItem('portal_token')
  userClientConfig.value = null
  myGrantedToolIds.value = new Set()
  myRequests.value = []
  myMcpsList.value = []
  toast.info('已退出当前工号')
  loadUserConfigAndGrants()
}

function toggleUserMenu() {
  userMenuVisible.value = !userMenuVisible.value
}

function handleMenuMyRequests() {
  userMenuVisible.value = false
  openMyRequestsDrawer()
}

function handleMenuGuide() {
  userMenuVisible.value = false
  guideModalVisible.value = true
}

function handleDocumentClick(e: MouseEvent) {
  if (userMenuRef.value && !userMenuRef.value.contains(e.target as Node)) {
    userMenuVisible.value = false
  }
}

function promptSwitchUser() {
  openLoginModal()
}

async function loadUserConfigAndGrants() {
  if (!isLoggedIn.value || !currentUserId.value) {
    userClientConfig.value = null
    myGrantedToolIds.value = new Set()
    myRequests.value = []
    myMcpsList.value = []
    return
  }
  try {
    const [cfg, grants, reqs] = await Promise.all([
      getPortalMyConfig(currentUserId.value),
      getPortalMyGrants(currentUserId.value),
      getPortalMyRequests(currentUserId.value).catch(() => []),
      loadMyMcps().catch(() => [])
    ])
    userClientConfig.value = cfg
    myGrantedToolIds.value = new Set(grants.granted_tool_ids || [])
    if (reqs && Array.isArray(reqs)) {
      myRequests.value = reqs
    }
  } catch (err) {
    console.warn('加载用户 Token 与权限失败:', err)
  }
}

function isToolL0(tool: any): boolean {
  return (tool.risk_level || '').toUpperCase() === 'L0'
}

function isToolGranted(tool: any): boolean {
  if (isToolL0(tool)) return true
  const tid = tool.id || tool.namespace_name || tool.name
  return (
    myGrantedToolIds.value.has(tid) ||
    myGrantedToolIds.value.has(tool.name) ||
    myGrantedToolIds.value.has(tool.namespace_name)
  )
}

function isToolSelectable(tool: any): boolean {
  return !isToolL0(tool) && !isToolGranted(tool)
}

/**
 * 从普通用户/业务人员角度获取工具的大标题显示名称
 * 避免直接展示底层 message__send_notification 这类技术标识符
 */
function getToolBusinessTitle(tool: any): string {
  if (!tool) return '未知功能'

  // 1. 常见业务功能命名空间字典精准映射
  const rawName = tool.name || tool.namespace_name || ''
  const cleanName = rawName.includes('__') ? rawName.split('__')[1] : rawName

  const knownMap: Record<string, string> = {
    send_notification: '发送消息通知',
    list_pending: '查询待办消息列表',
    portfolio_summary: '投资组合汇总分析',
    market_quotes: '实时市场行情查询',
    risk_assessment: '资产风险合规评估',
    document_export: '业务文档格式导出',
    search_docs: '业务知识文档检索',
    export_pdf: '导出为 PDF 报告',
    export_excel: '导出为 Excel 表格',
  }

  if (knownMap[cleanName]) {
    return knownMap[cleanName]
  }

  // 2. 如果描述本身就是精炼的业务说明（如 <= 22 字符），直接作为大标题
  if (tool.description && tool.description.trim()) {
    const desc = tool.description.trim()
    const firstSentence = desc.split(/[。；;\n]/)[0].trim()
    if (firstSentence && firstSentence.length <= 18) {
      return firstSentence
    }
    if (desc.length <= 22) {
      return desc
    }
  }

  // 3. 截取描述前段
  if (tool.description && tool.description.trim()) {
    return tool.description.trim().slice(0, 16) + (tool.description.trim().length > 16 ? '...' : '')
  }

  // 4. 下划线转换为可读词组
  const words = cleanName.split(/[_-]/).filter(Boolean)
  if (words.length > 0) {
    return words.map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
  }

  return rawName || '未知功能'
}

/**
 * 获取工具的业务场景说明（通俗可读）
 */
function getToolBusinessDesc(tool: any): string {
  if (!tool) return ''
  const title = getToolBusinessTitle(tool)
  if (tool.description && tool.description.trim()) {
    const desc = tool.description.trim()
    if (desc === title) {
      return isToolL0(tool)
        ? '基础只读功能，连接本服务后在 AI 客户端中输入自然语言即可直接调用。'
        : '涉及业务写入或敏感数据，需勾选申请开通后方可在 AI 对话中启用。'
    }
    return desc
  }
  return isToolL0(tool)
    ? '基础公开功能，无需特殊授权，接入后可直接在 AI 助手中消费。'
    : '敏感业务操作能力，需提交审批开通方可在本地客户端点亮。'
}

function toggleToolSelection(tool: any) {
  const tid = tool.id || tool.namespace_name || tool.name
  if (selectedToolIdsForApply.value.has(tid)) {
    selectedToolIdsForApply.value.delete(tid)
  } else {
    selectedToolIdsForApply.value.add(tid)
  }
}

function toggleSelectAllNonL0() {
  if (!currentDetail.value) return
  const selectable = currentDetail.value.tools.filter(t => isToolSelectable(t))
  const allSelected = selectable.every(t =>
    selectedToolIdsForApply.value.has(t.id || t.namespace_name || t.name)
  )
  if (allSelected) {
    selectable.forEach(t => selectedToolIdsForApply.value.delete(t.id || t.namespace_name || t.name))
  } else {
    selectable.forEach(t => selectedToolIdsForApply.value.add(t.id || t.namespace_name || t.name))
  }
}

function getSelectedToolsForApplySummary() {
  if (!currentDetail.value) return []
  return currentDetail.value.tools
    .filter(t => selectedToolIdsForApply.value.has(t.id || t.namespace_name || t.name))
    .map(t => ({
      id: t.id || t.namespace_name || t.name,
      name: getToolBusinessTitle(t),
      techName: t.name,
      risk: t.risk_level,
    }))
}

function openApplyModal() {
  if (!isLoggedIn.value) {
    toast.info('提交功能权限申请需先绑定您的企业工号，请先登录')
    openLoginModal()
    return
  }
  if (selectedToolIdsForApply.value.size === 0) {
    toast.warning('请先勾选需要申请开通的功能')
    return
  }
  applyReason.value = ''
  applyCredentialForm.value = {}
  showCustomCredInApply.value = false
  applyModalVisible.value = true
}

async function submitPermissionApplication() {
  if (!currentDetail.value) return
  if (!applyReason.value.trim()) {
    toast.warning('请填写业务申请说明')
    return
  }

  // 仅当本次勾选的工具中有需凭据工具时，才校验并传递个人业务凭据
  const hasExisting = Boolean(currentServiceExistingBinding.value)
  const credCheck = validateCredentialFormForSelectedTools(
    currentDetail.value,
    selectedToolIdsForApply.value,
    hasExisting,
    showCustomCredInApply.value,
    applyCredentialForm.value,
  )
  if (!credCheck.valid) {
    toast.warning(`请填写必填业务凭据: ${credCheck.missingFieldLabel}`)
    return
  }

  const requestPayload = buildPermissionRequestPayload({
    userId: currentUserId.value,
    userName: currentUserName.value,
    detail: currentDetail.value,
    selectedToolIds: selectedToolIdsForApply.value,
    reason: applyReason.value,
    hasExistingBinding: hasExisting,
    showCustomCredInApply: showCustomCredInApply.value,
    credentialForm: applyCredentialForm.value,
  })

  submittingApply.value = true
  try {
    await createPortalPermissionRequest(requestPayload)
    toast.success('权限申请已提交，待管理员审批通过后即可使用！')
    applyModalVisible.value = false
    selectedToolIdsForApply.value.clear()
    applyCredentialForm.value = {}
    showCustomCredInApply.value = false
    await Promise.all([loadUserConfigAndGrants(), loadMyMcps()])
  } catch (err: any) {
    toast.error('提交申请失败，请稍后重试')
  } finally {
    submittingApply.value = false
  }
}

async function loadMyMcps() {
  if (!isLoggedIn.value) {
    myMcpsList.value = []
    return
  }
  loadingMyMcps.value = true
  try {
    myMcpsList.value = await getPortalMyMcps()
  } catch (err) {
    console.warn('获取我添加的 MCP 列表失败:', err)
  } finally {
    loadingMyMcps.value = false
  }
}

function handleMenuMyMcps() {
  userMenuVisible.value = false
  myMcpsDrawerVisible.value = true
  loadMyMcps()
}

function openEditBindingDialog(item: UserMcpDetail) {
  editingMcpItem.value = item
  editBindingForm.value = {
    username: item.credential_summary?.username || '',
    password: '',
  }
  editBindingModalVisible.value = true
}

async function submitEditBinding() {
  if (!editingMcpItem.value) return
  if (!editBindingForm.value.username.trim()) {
    toast.warning('请输入业务用户名')
    return
  }
  submittingEditBinding.value = true
  try {
    const payload: Record<string, any> = {
      username: editBindingForm.value.username.trim(),
    }
    if (editBindingForm.value.password) {
      payload.password = editBindingForm.value.password
    }
    await updatePortalServiceBinding(editingMcpItem.value.service_id, payload)
    toast.success('业务凭据已更新，原 Session 已失效')
    editBindingModalVisible.value = false
    await loadMyMcps()
  } catch (err: any) {
    toast.error('保存凭据失败，请重试')
  } finally {
    submittingEditBinding.value = false
  }
}

async function handleUnbindService(item: UserMcpDetail) {
  if (!confirm(`确定要解绑 ${item.service_name} 的个人业务凭据吗？解绑后将立即阻止后续需要此绑定的工具调用。`)) {
    return
  }
  try {
    await unbindPortalServiceBinding(item.service_id)
    toast.success(`已解绑 ${item.service_name} 的业务凭据`)
    await loadMyMcps()
  } catch (err: any) {
    toast.error('解绑失败，请重试')
  }
}

async function openMyRequestsDrawer() {
  myRequestsDrawerVisible.value = true
  await loadMyRequests()
}

async function loadMyRequests() {
  loadingMyRequests.value = true
  try {
    myRequests.value = await getPortalMyRequests(currentUserId.value)
  } catch (err) {
    toast.error('加载申请历史失败')
  } finally {
    loadingMyRequests.value = false
  }
}

function openAccessModalFromDetail() {
  if (!currentDetail.value) return
  selectedCap.value = {
    id: currentDetail.value.id,
    name: currentDetail.value.name,
    description: currentDetail.value.description,
    category: currentDetail.value.category,
    tools_count: currentDetail.value.tools.length,
    status: currentDetail.value.status,
    auth_mode: currentDetail.value.auth_mode,
    auth_label: currentDetail.value.auth_label,
    call_count: currentDetail.value.total_calls,
    recent_calls_7d: currentDetail.value.recent_calls_7d,
    last_active_at: currentDetail.value.last_active_at,
    created_at: currentDetail.value.created_at,
  }
  detailDrawerVisible.value = false
  accessModalVisible.value = true
}

function toggleToolSchema(toolName: string) {
  if (expandedTools.value.has(toolName)) {
    expandedTools.value.delete(toolName)
  } else {
    expandedTools.value.add(toolName)
  }
}

async function copyText(text: string, label: string = '内容') {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      // 兼容离线低权限/老版本浏览器 execCommand 回退
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    toast.success(`${label}已复制到剪贴板`)
  } catch (err) {
    toast.error('复制失败，请手动选择复制')
  }
}

function handlePrimaryCopy() {
  if (activeAccessTab.value === 'form') {
    copyText(currentGatewayUrlWithToken.value, '统一 MCP 服务地址')
  } else if (activeAccessTab.value === 'json') {
    copyText(generatedMcpJson.value, '标准 JSON 配置')
  } else {
    copyText(generatedNaturalLanguagePrompt.value, '自然语言接入指令')
  }
}

function handleAuthAction() {
  if (selectedCap.value && (selectedCap.value as any).auth_entry_url) {
    window.open((selectedCap.value as any).auth_entry_url, '_blank')
  } else {
    toast.info('当前服务已接入平台统一认证托管，在 AI 助手首次发起调用时将自动完成校验。')
  }
}

function handleGlobalKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    searchInputRef.value?.focus()
    searchInputRef.value?.select()
  }
}

onMounted(() => {
  loadOverview()
  loadCapabilities()
  loadUserConfigAndGrants()
  window.addEventListener('keydown', handleGlobalKeydown)
  document.addEventListener('click', handleDocumentClick)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<style scoped>
.portal-root {
  min-height: 100vh;
  width: 100vw;
  background-color: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface);
  display: flex;
  flex-direction: column;
}

/* 1. Header */
.portal-header {
  position: sticky;
  top: 0;
  z-index: 40;
  background-color: color-mix(in srgb, var(--md-sys-color-surface) 88%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  height: 64px;
}

.portal-header__inner {
  max-width: 1360px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  gap: 20px;
}

.brand-group {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  user-select: none;
}

.brand-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--md-sys-shape-corner-medium, 10px);
  background: linear-gradient(135deg, var(--md-sys-color-primary), var(--md-sys-color-primary-container));
  color: var(--md-sys-color-on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-text {
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.2px;
  color: var(--md-sys-color-on-surface);
}

.brand-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  border-radius: 9999px;
}

.header-search {
  flex: 1;
  max-width: 520px;
  height: 40px;
  background-color: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-full, 9999px);
  display: flex;
  align-items: center;
  padding: 0 14px;
  gap: 8px;
  transition: all 0.2s ease;
}

.header-search:focus-within {
  background-color: var(--md-sys-color-surface-container-high);
  border-color: var(--md-sys-color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--md-sys-color-primary) 15%, transparent);
}

.search-icon {
  color: var(--md-sys-color-outline);
}

.search-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-size: 13.5px;
  color: var(--md-sys-color-on-surface);
}

.search-input::placeholder {
  color: var(--md-sys-color-outline);
}

.search-clear-btn {
  background: transparent;
  border: none;
  color: var(--md-sys-color-outline);
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 2px;
}

.search-shortcut {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  font-weight: 500;
  color: var(--md-sys-color-outline);
  background-color: var(--md-sys-color-surface-container-highest);
  padding: 2px 6px;
  border-radius: 4px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border-radius: var(--md-sys-shape-corner-full, 9999px);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.global-access-btn {
  background: linear-gradient(135deg, var(--md-sys-color-primary), #6366f1);
  color: #ffffff;
  border: none;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--md-sys-color-primary) 35%, transparent);
}

.global-access-btn:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--md-sys-color-primary) 45%, transparent);
}

.login-btn {
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-primary);
  border: 1px solid var(--md-sys-color-outline-variant);
  font-weight: 600;
}

.login-btn:hover {
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  border-color: var(--md-sys-color-primary);
}

.icon-action-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
}

.icon-action-btn:hover {
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
}

.header-divider {
  width: 1px;
  height: 20px;
  background-color: var(--md-sys-color-outline-variant);
}

/* 用户头像胶囊与下拉菜单 */
.user-menu-container {
  position: relative;
}

.user-profile-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 10px 0 5px;
  border-radius: var(--md-sys-shape-corner-full, 9999px);
  background-color: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
  transition: all 0.2s ease;
}

.user-profile-trigger:hover,
.user-profile-trigger.is-active {
  background-color: var(--md-sys-color-surface-container-high);
  border-color: var(--md-sys-color-primary);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.user-avatar-circle {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--md-sys-color-primary), #06b6d4);
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  flex-shrink: 0;
}

.user-status-dot {
  position: absolute;
  bottom: -1px;
  right: -1px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #22c55e;
  border: 1.5px solid var(--md-sys-color-surface);
}

.user-trigger-info {
  display: flex;
  flex-direction: column;
  text-align: left;
  line-height: 1.2;
}

.user-trigger-name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-trigger-id {
  font-size: 10.5px;
  color: var(--md-sys-color-outline);
}

.user-trigger-arrow {
  color: var(--md-sys-color-outline);
  transition: transform 0.2s ease;
}

.user-trigger-arrow.is-flipped {
  transform: rotate(180deg);
}

/* 下拉卡片 */
.user-dropdown-card {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 280px;
  background-color: var(--md-sys-color-surface-container-high);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-large, 16px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15), 0 2px 6px rgba(0, 0, 0, 0.08);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 50;
}

.user-dropdown-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px;
}

.user-card-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--md-sys-color-primary), #06b6d4);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-card-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-card-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.user-card-name {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-badge {
  font-size: 10.5px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 500;
}

.role-badge.admin {
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-primary);
  font-weight: 600;
}

.role-badge.user {
  background-color: var(--md-sys-color-surface-container-highest);
  color: var(--md-sys-color-on-surface-variant);
}

.user-card-id {
  font-size: 11px;
  color: var(--md-sys-color-outline);
}

.user-grants-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--md-sys-color-on-surface-variant);
  background-color: var(--md-sys-color-surface-container);
  padding: 7px 10px;
  border-radius: 8px;
}

.dropdown-divider {
  height: 1px;
  background-color: var(--md-sys-color-outline-variant);
  margin: 2px 0;
}

.user-menu-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.dropdown-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.dropdown-menu-item:hover {
  background-color: var(--md-sys-color-surface-container-highest);
}

.dropdown-menu-item .item-icon {
  color: var(--md-sys-color-on-surface-variant);
  flex-shrink: 0;
}

.dropdown-menu-item.admin-highlight-item {
  background-color: color-mix(in srgb, var(--md-sys-color-primary-container) 35%, transparent);
  border: 1px dashed color-mix(in srgb, var(--md-sys-color-primary) 60%, transparent);
  margin-top: 2px;
}

.dropdown-menu-item.admin-highlight-item:hover {
  background-color: var(--md-sys-color-primary-container);
  border-style: solid;
}

.admin-item-text {
  display: flex;
  flex-direction: column;
  text-align: left;
}

.admin-item-title {
  font-weight: 600;
  color: var(--md-sys-color-primary);
  font-size: 13px;
}

.admin-item-sub {
  font-size: 10.5px;
  color: var(--md-sys-color-outline);
}

.badge-count {
  margin-left: auto;
  background-color: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 9999px;
}

.user-menu-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 4px;
}

.dropdown-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  border: none;
  background: transparent;
  color: var(--md-sys-color-outline);
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.dropdown-action-btn:hover {
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface);
}

.dropdown-action-btn.logout-text:hover {
  color: var(--md-sys-color-error);
}

/* 快捷工号登录弹窗样式 */
.login-modal-content {
  padding: 6px 0;
}

.demo-quick-section {
  padding-top: 14px;
  border-top: 1px dashed var(--md-sys-color-outline-variant);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.demo-quick-title {
  font-size: 11.5px;
  color: var(--md-sys-color-outline);
}

.demo-quick-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.demo-tag-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 9999px;
  font-size: 11.5px;
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
  transition: all 0.2s ease;
}

.demo-tag-btn:hover {
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-primary);
  border-color: var(--md-sys-color-primary);
}

.demo-tag-btn.is-active {
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-primary);
  border-color: var(--md-sys-color-primary);
  font-weight: 600;
}

.demo-tag-btn.admin {
  color: var(--md-sys-color-tertiary);
}

.demo-tag-btn.admin:hover,
.demo-tag-btn.admin.is-active {
  background-color: color-mix(in srgb, var(--md-sys-color-tertiary-container) 40%, transparent);
  border-color: var(--md-sys-color-tertiary);
  color: var(--md-sys-color-tertiary);
}

/* 下拉菜单动画 */
.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.98);
}

/* 接入弹窗身份绑定状态条 */
.user-binding-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--md-sys-shape-corner-medium, 10px);
  font-size: 12.5px;
  line-height: 1.4;
}

.user-binding-banner.is-logged-in {
  background-color: color-mix(in srgb, var(--md-sys-color-primary-container) 30%, transparent);
  border: 1px solid color-mix(in srgb, var(--md-sys-color-primary) 30%, transparent);
  color: var(--md-sys-color-on-surface);
}

.user-binding-banner.is-guest {
  background-color: color-mix(in srgb, #f59e0b 12%, transparent);
  border: 1px solid color-mix(in srgb, #f59e0b 35%, transparent);
  color: var(--md-sys-color-on-surface);
}

.binding-text {
  flex: 1;
}

.quick-login-link-btn {
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  border: none;
  font-size: 11.5px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 9999px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.quick-login-link-btn:hover {
  filter: brightness(1.1);
}

/* 2. Hero Section */
.portal-hero {
  padding: 40px 24px 32px 24px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--md-sys-color-primary-container) 12%, transparent) 0%,
    transparent 100%
  );
}

.hero-container {
  max-width: 1360px;
  margin: 0 auto;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-primary);
  border-radius: 9999px;
  border: 1px solid var(--md-sys-color-outline-variant);
  margin-bottom: 14px;
}

.hero-title {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.5px;
  line-height: 1.3;
  color: var(--md-sys-color-on-surface);
  margin-bottom: 8px;
}

.hero-desc {
  font-size: 14px;
  line-height: 1.6;
  color: var(--md-sys-color-on-surface-variant);
  max-width: 760px;
  margin-bottom: 28px;
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  border-radius: var(--md-sys-shape-corner-large, 16px);
  background-color: var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.stat-icon-wrapper {
  width: 44px;
  height: 44px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.bg-primary-soft {
  background-color: var(--md-sys-color-primary-container);
}
.bg-secondary-soft {
  background-color: var(--md-sys-color-secondary-container);
}
.bg-success-soft {
  background-color: color-mix(in srgb, #198754 15%, transparent);
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--md-sys-color-on-surface);
}

.stat-label {
  font-size: 12px;
  color: var(--md-sys-color-outline);
  margin-top: 2px;
}

.trend-stat-card {
  flex-direction: column;
  align-items: stretch;
  justify-content: space-between;
}

.trend-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.trend-total {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--md-sys-color-primary);
}

.mini-trend-bar-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 6px;
  height: 42px;
  margin-top: 8px;
}

.mini-bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}

.mini-bar-track {
  flex: 1;
  width: 100%;
  max-width: 14px;
  background-color: var(--md-sys-color-surface-container-highest);
  border-radius: 4px;
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}

.mini-bar-fill {
  width: 100%;
  background-color: var(--md-sys-color-primary);
  border-radius: 4px;
  transition: height 0.3s ease;
}

.mini-bar-day {
  font-size: 9.5px;
  color: var(--md-sys-color-outline);
  margin-top: 4px;
}

/* 3. Main Discovery Section */
.portal-main {
  flex: 1;
  padding: 32px 24px 64px 24px;
}

.main-container {
  max-width: 1360px;
  margin: 0 auto;
}

.discovery-filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 24px;
}

.category-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.category-tab-btn {
  padding: 6px 16px;
  border-radius: 9999px;
  font-size: 13px;
  font-weight: 500;
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.category-tab-btn:hover {
  background-color: var(--md-sys-color-surface-container-high);
}

.category-tab-btn.is-active {
  background-color: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  border-color: var(--md-sys-color-primary);
}

.sort-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sort-label {
  font-size: 12.5px;
  color: var(--md-sys-color-outline);
}

.sort-options {
  display: flex;
  background-color: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-medium, 10px);
  padding: 3px;
  gap: 2px;
}

.sort-opt-btn {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  background: transparent;
  border: none;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  transition: all 0.2s ease;
}

.sort-opt-btn.is-active {
  background-color: var(--md-sys-color-surface);
  color: var(--md-sys-color-primary);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* Capabilities Grid */
.capabilities-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.cap-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 22px;
  border-radius: var(--md-sys-shape-corner-large, 18px);
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.cap-card:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 50%, transparent);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}

.cap-card__header {
  display: flex;
  gap: 14px;
}

.cap-card__avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cap-card__title-area {
  flex: 1;
  min-width: 0;
}

.cap-card__name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.cap-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-indicator.is-active {
  background-color: #198754;
  box-shadow: 0 0 0 2px rgba(25, 135, 84, 0.2);
}

.status-indicator.is-degraded {
  background-color: #f59e0b;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2);
}

.cap-card__tags {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.category-pill {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 9999px;
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.auth-pill {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 9999px;
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.cap-card__desc {
  font-size: 13.5px;
  line-height: 1.55;
  color: var(--md-sys-color-on-surface-variant);
  margin-top: 14px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 42px;
}

.cap-card__metrics {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0 14px 0;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  margin-top: 16px;
  font-size: 12.5px;
  color: var(--md-sys-color-on-surface-variant);
}

.metric-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.metric-item strong {
  color: var(--md-sys-color-on-surface);
  font-weight: 600;
}

.cap-card__footer {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding-top: 10px;
}

.cap-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 38px;
  border-radius: var(--md-sys-shape-corner-medium, 10px);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.detail-btn {
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.detail-btn:hover {
  background-color: var(--md-sys-color-surface-container-high);
}

.access-btn {
  background-color: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
  border: 1px solid transparent;
}

.access-btn:hover {
  background-color: color-mix(in srgb, var(--md-sys-color-secondary-container) 90%, black);
  box-shadow: var(--md-elevation-1);
}

/* 4. Empty State */
.empty-portal-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;
}

.empty-icon-circle {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background-color: var(--md-sys-color-surface-container-high);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.reset-search-btn {
  padding: 8px 18px;
  border-radius: 9999px;
  font-size: 13px;
  font-weight: 500;
  background-color: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  border: none;
  cursor: pointer;
}

/* 5. Access Modal Styles */
.access-panel {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 6px 0;
}

.aggregation-banner {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.banner-icon {
  flex-shrink: 0;
  margin-top: 2px;
}

.banner-title {
  font-size: 13px;
  font-weight: 600;
}

.banner-text {
  font-size: 12px;
  line-height: 1.5;
  margin-top: 2px;
  opacity: 0.9;
}

.access-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  background-color: var(--md-sys-color-surface-container);
  padding: 4px;
  border-radius: var(--md-sys-shape-corner-medium, 10px);
}

.access-tab-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  background: transparent;
  border: none;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  min-width: 0;
  overflow: hidden;
}

.access-tab-btn span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.access-tab-btn.is-active {
  background-color: var(--md-sys-color-surface);
  color: var(--md-sys-color-primary);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.tab-pane {
  background-color: var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  padding: 16px 18px;
}

.field-copy-group {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}

.field-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background-color: var(--md-sys-color-surface);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-medium, 8px);
  gap: 10px;
}

.highlight-box {
  border-color: var(--md-sys-color-primary);
  background-color: color-mix(in srgb, var(--md-sys-color-primary-container) 20%, var(--md-sys-color-surface));
}

.field-val {
  font-size: 13px;
  color: var(--md-sys-color-on-surface);
}

.mono {
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.break-all {
  word-break: break-all;
}

.copy-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.copy-pill-btn:hover {
  background-color: var(--md-sys-color-surface-container-highest);
}

.copy-pill-btn.primary {
  background-color: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  border-color: var(--md-sys-color-primary);
}

.code-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.code-title {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--md-sys-color-on-surface-variant);
  flex: 1;
  min-width: 0;
}

.code-preview {
  background-color: var(--md-sys-color-surface-container-highest);
  color: var(--md-sys-color-on-surface);
  padding: 14px;
  border-radius: var(--md-sys-shape-corner-medium, 10px);
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.45;
  overflow: auto;
  max-height: 280px;
  border: 1px solid var(--md-sys-color-outline-variant);
}

.natural-prompt-box {
  background-color: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface);
  padding: 16px;
  border-radius: var(--md-sys-shape-corner-medium, 10px);
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  overflow-wrap: anywhere;
  border: 1px solid var(--md-sys-color-outline-variant);
  max-height: 320px;
  overflow-y: auto;
}

/* 认证通知卡片 */
.auth-notice-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  background-color: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.auth-notice-left {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  flex: 1;
  min-width: 0;
}

.shield-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--md-sys-color-primary-container);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.auth-notice-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.auth-notice-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}

.auth-badge-small {
  font-size: 10.5px;
  font-weight: 500;
  padding: 1px 6px;
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-primary);
  border-radius: 4px;
}

.auth-notice-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--md-sys-color-on-surface-variant);
  margin-top: 3px;
  word-break: break-word;
}

.auth-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 7px 14px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  background-color: var(--md-sys-color-surface);
  color: var(--md-sys-color-primary);
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.auth-action-btn:hover {
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.modal-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 6. Detail Drawer Styles */
.detail-drawer-body {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 8px 0;
}

.detail-hero-card {
  padding: 20px;
  border-radius: var(--md-sys-shape-corner-large, 16px);
  background-color: var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.detail-title-row {
  display: flex;
  gap: 14px;
  align-items: center;
}

.detail-avatar {
  width: 52px;
  height: 52px;
  border-radius: var(--md-sys-shape-corner-medium, 14px);
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.detail-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
}

.detail-tags-row {
  display: flex;
  gap: 6px;
  align-items: center;
}

.version-pill {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-outline);
}

.detail-desc {
  font-size: 14px;
  line-height: 1.6;
  color: var(--md-sys-color-on-surface-variant);
}

.detail-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding-top: 14px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
}

.detail-stat-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.stat-num {
  font-size: 18px;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
}

.stat-sub {
  font-size: 11.5px;
  color: var(--md-sys-color-outline);
  margin-top: 2px;
}

/* 3 步指引 */
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
  margin-bottom: 12px;
}

.three-steps {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.step-card {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--md-sys-shape-corner-medium, 10px);
  background-color: var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
  align-items: flex-start;
}

.step-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background-color: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 1px;
}

.step-body {
  display: flex;
  flex-direction: column;
}

.step-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}

.step-text {
  font-size: 11px;
  color: var(--md-sys-color-on-surface-variant);
  margin-top: 2px;
  line-height: 1.35;
}

/* 场景提问 */
.examples-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.example-pill-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-radius: var(--md-sys-shape-corner-medium, 10px);
  background-color: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
  transition: all 0.2s ease;
}

.example-pill-item:hover {
  background-color: var(--md-sys-color-surface-container-high);
  border-color: var(--md-sys-color-primary);
}

.example-content {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--md-sys-color-on-surface);
}

.example-quote-icon {
  color: var(--md-sys-color-primary);
  flex-shrink: 0;
}

.example-copy-btn {
  background: transparent;
  border: none;
  color: var(--md-sys-color-outline);
  cursor: pointer;
}

/* 工具清单 */
.tools-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.tools-accordion-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tool-accordion-card {
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  border: 1px solid var(--md-sys-color-outline-variant);
  background-color: var(--md-sys-color-surface-container-lowest);
  overflow: hidden;
  transition: all 0.2s ease;
}

.tool-accordion-card:hover {
  border-color: color-mix(in srgb, var(--md-sys-color-primary) 35%, var(--md-sys-color-outline-variant));
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.tool-accordion-card.is-selected-for-apply {
  border-color: var(--md-sys-color-primary);
  background-color: color-mix(in srgb, var(--md-sys-color-primary) 5%, var(--md-sys-color-surface));
}

.tool-summary-row {
  display: flex;
  align-items: flex-start;
  padding: 14px 16px;
  gap: 12px;
}

/* 左侧统一对齐槽位 (固定 24px) */
.tool-col-action {
  width: 24px;
  min-width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
  flex-shrink: 0;
}

.tool-select-checkbox-label {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  width: 24px;
  height: 24px;
}

.tool-checkbox {
  width: 17px;
  height: 17px;
  cursor: pointer;
  accent-color: var(--md-sys-color-primary);
  margin: 0;
}

.tool-status-icon-slot {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
}

.text-emerald-500 {
  color: #10b981;
}

/* 中间业务内容区 */
.tool-col-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tool-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 业务中文大标题 */
.tool-business-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
  line-height: 1.35;
}

/* 微型技术方法标识符 (低调展示) */
.tool-tech-slug {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 11px;
  color: var(--md-sys-color-on-surface-variant);
  background-color: var(--md-sys-color-surface-container-high);
  padding: 1px 6px;
  border-radius: 4px;
  line-height: 1.4;
}

/* 业务状态胶囊 */
.perm-pill {
  font-size: 11px;
  font-weight: 500;
  padding: 1.5px 8px;
  border-radius: 9999px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  line-height: 1.4;
  white-space: nowrap;
}

.pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.pill-dot.bg-emerald {
  background-color: #10b981;
}

.pill-dot.bg-primary {
  background-color: var(--md-sys-color-primary);
}

.pill-dot.bg-amber {
  background-color: #f59e0b;
}

.perm-pill.pill-l0 {
  background-color: rgba(16, 185, 129, 0.1);
  color: #059669;
  border: 1px solid rgba(16, 185, 129, 0.25);
}

.perm-pill.pill-granted {
  background-color: color-mix(in srgb, var(--md-sys-color-primary) 10%, transparent);
  color: var(--md-sys-color-primary);
  border: 1px solid color-mix(in srgb, var(--md-sys-color-primary) 25%, transparent);
}

.perm-pill.pill-need-apply {
  background-color: rgba(245, 158, 11, 0.1);
  color: #d97706;
  border: 1px solid rgba(245, 158, 11, 0.25);
}

.perm-pill.pill-confirm {
  background-color: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

/* 业务描述 */
.tool-business-desc {
  font-size: 13px;
  color: var(--md-sys-color-on-surface-variant);
  line-height: 1.5;
  margin: 0;
}

/* 右侧折叠按钮 */
.tool-col-toggle {
  flex-shrink: 0;
  margin-top: 1px;
}

.schema-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  color: var(--md-sys-color-outline);
  background: transparent;
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
  padding: 3px 8px;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.schema-toggle-btn:hover {
  color: var(--md-sys-color-primary);
  border-color: var(--md-sys-color-primary);
  background-color: var(--md-sys-color-surface-container);
}

.tool-schema-collapse {
  padding: 12px 16px 16px 16px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  background-color: var(--md-sys-color-surface-container-low);
}

.schema-code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.schema-code-label {
  font-size: 11px;
  color: var(--md-sys-color-outline);
}

.copy-text-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--md-sys-color-primary);
  background: transparent;
  border: none;
  cursor: pointer;
}

.schema-code-block {
  background-color: var(--md-sys-color-surface-container-highest);
  color: var(--md-sys-color-on-surface);
  padding: 12px;
  border-radius: var(--md-sys-shape-corner-medium, 8px);
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  line-height: 1.4;
  overflow: auto;
  max-height: 180px;
}

/* 抽屉底部快捷接入卡片 (布局强化，消除换行与挤压) */
.detail-drawer-footer-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  border-radius: var(--md-sys-shape-corner-large, 14px);
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--md-sys-color-primary-container) 35%, var(--md-sys-color-surface-container)) 0%,
    var(--md-sys-color-surface-container) 100%
  );
  border: 1px solid var(--md-sys-color-outline-variant);
  margin-top: 14px;
}

.drawer-footer-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.drawer-footer-text .footer-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}

.drawer-footer-text .footer-hint {
  font-size: 12px;
  color: var(--md-sys-color-on-surface-variant);
  line-height: 1.4;
  white-space: normal;
}

.drawer-footer-actions-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  white-space: nowrap;
}

.apply-perm-btn,
.access-highlight-btn {
  white-space: nowrap !important;
  flex-shrink: 0 !important;
  height: 38px !important;
  padding: 0 16px !important;
  border-radius: 9999px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 6px !important;
  cursor: pointer;
  transition: all 0.2s ease;
  line-height: 1 !important;
}

.apply-perm-btn {
  background-color: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  border: 1px solid transparent;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
}

.apply-perm-btn:hover {
  opacity: 0.92;
  transform: translateY(-1px);
}

.access-highlight-btn {
  background-color: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.access-highlight-btn:hover {
  background-color: var(--md-sys-color-surface-container-high);
  border-color: var(--md-sys-color-outline);
}

/* 7. Guide Modal */
.guide-modal-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 10px 0;
}

.guide-step-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.guide-step-badge {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 700;
  flex-shrink: 0;
}

.guide-step-heading {
  font-size: 15px;
  font-weight: 700;
  color: var(--md-sys-color-on-surface);
}

.guide-step-body {
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--md-sys-color-on-surface-variant);
  margin-top: 4px;
}

/* Skeleton Loading */
.cards-skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.skeleton-card {
  padding: 22px;
  border-radius: var(--md-sys-shape-corner-large, 18px);
  background-color: var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.skeleton-header {
  display: flex;
  gap: 14px;
  align-items: center;
}

.skeleton-avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background-color: var(--md-sys-color-surface-container-highest);
  animation: pulse 1.5s infinite ease-in-out;
}

.skeleton-title-lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-line {
  height: 12px;
  border-radius: 6px;
  background-color: var(--md-sys-color-surface-container-highest);
  animation: pulse 1.5s infinite ease-in-out;
}

.w-20 { width: 20%; }
.w-30 { width: 30%; }
.w-40 { width: 40%; }
.w-80 { width: 80%; }
.w-full { width: 100%; }
.mt-1 { margin-top: 4px; }
.mt-2 { margin-top: 8px; }
.mt-3 { margin-top: 12px; }
.mt-4 { margin-top: 16px; }
.mt-6 { margin-top: 24px; }

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 0.3; }
}

@media (max-width: 768px) {
  .portal-header__inner {
    padding: 0 16px;
  }
  .header-search {
    display: none;
  }
  .three-steps {
    grid-template-columns: 1fr;
  }
  .access-tabs {
    grid-template-columns: 1fr;
  }
  .hero-title {
    font-size: 22px;
  }
}

/* --- 用户身份与权限申请新增样式 --- */
.user-identity-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  border-radius: 17px;
  border: 1px solid var(--md-sys-color-outline-variant);
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.user-identity-btn:hover {
  background-color: var(--md-sys-color-surface-container-highest);
  border-color: var(--md-sys-color-primary);
}
.user-id-text {
  font-family: var(--font-mono, monospace);
  font-weight: 600;
}

.reqs-btn {
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
  border: 1px solid var(--md-sys-color-outline-variant);
}
.reqs-btn:hover {
  background-color: var(--md-sys-color-surface-container-highest);
}

.tools-header-actions {
  display: flex;
  align-items: center;
}
.select-all-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--md-sys-color-outline-variant);
  background-color: var(--md-sys-color-surface-container-low);
  color: var(--md-sys-color-primary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.select-all-btn:hover {
  background-color: var(--md-sys-color-surface-container-high);
}

.tool-pill-tech {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 11px;
  color: var(--md-sys-color-outline);
  background-color: var(--md-sys-color-surface-container-high);
  padding: 1px 5px;
  border-radius: 4px;
}

.apply-modal-content {
  padding: 4px 0;
}
.apply-summary-banner {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  background-color: var(--md-sys-color-surface-container-high);
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--md-sys-color-on-surface);
}
.apply-form-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.selected-tools-pill-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 120px;
  overflow-y: auto;
  padding: 8px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 8px;
  background-color: var(--md-sys-color-surface-container-lowest);
}
.tool-apply-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  background-color: var(--md-sys-color-surface-container-high);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 4px;
  font-size: 12px;
}
.tool-pill-name {
  font-family: var(--font-mono, monospace);
  font-weight: 500;
}
.tool-pill-risk {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 3px;
  font-weight: 600;
}

.user-row-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.form-input, .form-textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 6px;
  background-color: var(--md-sys-color-surface-container-lowest);
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.form-input:focus, .form-textarea:focus {
  border-color: var(--md-sys-color-primary);
}

.my-requests-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}
.req-record-card {
  padding: 14px;
  border-radius: 8px;
  border: 1px solid var(--md-sys-color-outline-variant);
  background-color: var(--md-sys-color-surface-container-low);
}
.req-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.req-svc-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.req-id-tag {
  font-size: 11px;
  color: var(--md-sys-color-outline);
}
.req-status-pill {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 12px;
}
.req-status-pill.status-approved {
  background-color: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}
.req-status-pill.status-rejected {
  background-color: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}
.req-status-pill.status-pending {
  background-color: rgba(245, 158, 11, 0.12);
  color: #d97706;
}
.req-tools-box {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.req-tools-label {
  font-size: 12px;
}
.req-tool-tag {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  background-color: var(--md-sys-color-surface-container-high);
  font-family: var(--font-mono, monospace);
}
.req-comment-box {
  padding: 8px 10px;
  border-radius: 6px;
  background-color: var(--md-sys-color-surface-container-high);
}
.empty-requests-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  text-align: center;
}
</style>
