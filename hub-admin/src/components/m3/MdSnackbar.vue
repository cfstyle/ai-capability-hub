<script setup lang="ts">
import { useToast, type ToastType } from '@/composables/useToast'
import {
  CheckCircle2,
  AlertTriangle,
  Info,
  XCircle,
  X
} from 'lucide-vue-next'

const { toasts, dismiss } = useToast()

const getIcon = (type: ToastType) => {
  switch (type) {
    case 'success':
      return CheckCircle2
    case 'warning':
      return AlertTriangle
    case 'error':
      return XCircle
    case 'info':
    default:
      return Info
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="m3-snackbar-container" aria-live="polite" aria-atomic="true">
      <TransitionGroup name="m3-toast">
        <div
          v-for="item in toasts"
          :key="item.id"
          :class="['m3-snackbar-item', `m3-snackbar--${item.type}`]"
          role="alert"
        >
          <!-- 状态指示图标 -->
          <span class="m3-snackbar__icon">
            <component :is="getIcon(item.type)" :size="18" />
          </span>

          <!-- 消息正文 -->
          <span class="m3-snackbar__text type-body font-medium">
            {{ item.message }}
          </span>

          <!-- 关闭按钮 -->
          <button
            type="button"
            class="m3-snackbar__close md-state-layer"
            title="关闭通知"
            aria-label="关闭通知"
            @click="dismiss(item.id)"
          >
            <X :size="15" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
/* 默认固定于右下角 (bottom-6 right-6)，绝不遮挡顶部搜索框、主题色点与头像 */
.m3-snackbar-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: var(--z-toast, 70);
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
  max-width: 420px;
  width: calc(100vw - 48px);
}

.m3-snackbar-item {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  /* 使用 M3 Inverse Surface 与 Inverse On-Surface 进行高反差视觉呈现 */
  background-color: var(--md-sys-color-inverse-surface);
  color: var(--md-sys-color-inverse-on-surface);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18), 0 2px 4px rgba(0, 0, 0, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all var(--md-sys-motion-duration-medium1, 250ms) var(--md-easing-emphasized);
}

/* 深色模式下：inverse-surface 自动反转为浅灰白底 (#E3E3E3)，文字反转为深黑 (#141414) */
:global([data-theme="dark"]) .m3-snackbar-item,
:global(.dark) .m3-snackbar-item {
  border-color: rgba(0, 0, 0, 0.08);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35), 0 2px 6px rgba(0, 0, 0, 0.2);
}

.m3-snackbar__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* 浅色模式下：Snackbar 底色为深黑 (#2E2E2E)，图标采用高明度颜色 */
.m3-snackbar--success .m3-snackbar__icon {
  color: #4ade80;
}

.m3-snackbar--warning .m3-snackbar__icon {
  color: #facc15;
}

.m3-snackbar--error .m3-snackbar__icon {
  color: #f87171;
}

.m3-snackbar--info .m3-snackbar__icon {
  color: #60a5fa;
}

/* 深色模式下：Snackbar 底色反转为浅白 (#E3E3E3)，图标采用高对比深色，消除看不清的问题 */
:global([data-theme="dark"]) .m3-snackbar--success .m3-snackbar__icon,
:global(.dark) .m3-snackbar--success .m3-snackbar__icon {
  color: #15803d;
}

:global([data-theme="dark"]) .m3-snackbar--warning .m3-snackbar__icon,
:global(.dark) .m3-snackbar--warning .m3-snackbar__icon {
  color: #b45309;
}

:global([data-theme="dark"]) .m3-snackbar--error .m3-snackbar__icon,
:global(.dark) .m3-snackbar--error .m3-snackbar__icon {
  color: #b91c1c;
}

:global([data-theme="dark"]) .m3-snackbar--info .m3-snackbar__icon,
:global(.dark) .m3-snackbar--info .m3-snackbar__icon {
  color: #1d4ed8;
}

.m3-snackbar__text {
  flex: 1;
  word-break: break-word;
  font-size: 13.5px;
  line-height: 1.45;
  color: inherit;
}

.m3-snackbar__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--md-sys-shape-corner-full, 9999px);
  color: inherit;
  opacity: 0.75;
  cursor: pointer;
  background: transparent;
  border: none;
  flex-shrink: 0;
  transition: opacity var(--md-sys-motion-duration-short2) var(--md-easing-emphasized);
}

.m3-snackbar__close:hover {
  opacity: 1;
  background-color: color-mix(in srgb, currentColor 12%, transparent);
}

/* 动效过渡 (从下方轻盈升起淡入，向下滑出淡出) */
.m3-toast-enter-active,
.m3-toast-leave-active {
  transition: all 0.25s cubic-bezier(0.2, 0, 0, 1);
}

.m3-toast-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.96);
}

.m3-toast-leave-to {
  opacity: 0;
  transform: translateY(16px) scale(0.92);
}

/* 移动端自适应 (bottom-4 inset-x-4) */
@media (max-width: 599.98px) {
  .m3-snackbar-container {
    bottom: 16px;
    right: 16px;
    left: 16px;
    width: auto;
  }
}
</style>
