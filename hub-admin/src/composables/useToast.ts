import { ref } from 'vue'

export type ToastType = 'info' | 'success' | 'warning' | 'error'

export interface ToastMessage {
  id: string
  type: ToastType
  message: string
  duration?: number
  timerId?: ReturnType<typeof setTimeout>
}

const toasts = ref<ToastMessage[]>([])

export const useToast = () => {
  const show = (message: string, type: ToastType = 'info', duration = 3500) => {
    // 智能去重：如果在显示的 toasts 中已经存在完全相同的内容，直接刷新计时，避免多处 catch 或并发请求堆叠重复弹窗
    const existingIndex = toasts.value.findIndex((t) => t.message === message && t.type === type)
    if (existingIndex > -1) {
      const existing = toasts.value[existingIndex]
      if (existing && existing.timerId) {
        clearTimeout(existing.timerId)
        if (duration > 0) {
          existing.timerId = setTimeout(() => {
            dismiss(existing.id)
          }, duration)
        }
      }
      return existing?.id || ''
    }

    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
    const toastItem: ToastMessage = { id, type, message, duration }

    if (duration > 0) {
      toastItem.timerId = setTimeout(() => {
        dismiss(id)
      }, duration)
    }

    // 维持最多同时显示 4 条通知（避免右下角堆叠过长遮挡页面底部内容）
    if (toasts.value.length >= 4) {
      const oldest = toasts.value.shift()
      if (oldest?.timerId) {
        clearTimeout(oldest.timerId)
      }
    }

    toasts.value.push(toastItem)
    return id
  }

  const dismiss = (id: string) => {
    const idx = toasts.value.findIndex((t) => t.id === id)
    if (idx > -1) {
      const item = toasts.value[idx]
      if (item && item.timerId) {
        clearTimeout(item.timerId)
      }
      toasts.value.splice(idx, 1)
    }
  }

  const clear = () => {
    toasts.value.forEach((t) => {
      if (t.timerId) clearTimeout(t.timerId)
    })
    toasts.value = []
  }

  return {
    toasts,
    show,
    dismiss,
    clear,
    info: (msg: string, duration?: number) => show(msg, 'info', duration),
    success: (msg: string, duration?: number) => show(msg, 'success', duration),
    warning: (msg: string, duration?: number) => show(msg, 'warning', duration),
    error: (msg: string, duration?: number) => show(msg, 'error', duration)
  }
}
