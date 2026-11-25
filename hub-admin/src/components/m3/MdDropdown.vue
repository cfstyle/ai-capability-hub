<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { MoreHorizontal } from 'lucide-vue-next'

export interface DropdownItem {
  label: string
  key?: string
  icon?: any
  disabled?: boolean
  danger?: boolean
  onClick?: () => void
}

const props = withDefaults(
  defineProps<{
    items?: DropdownItem[]
    placement?: 'bottom-end' | 'bottom-start' | 'top-end' | 'top-start'
    disabled?: boolean
    minWidth?: string
  }>(),
  {
    items: () => [],
    placement: 'bottom-end',
    disabled: false,
    minWidth: '130px'
  }
)

const emit = defineEmits<{
  (e: 'select', item: DropdownItem): void
}>()

const isOpen = ref(false)
const triggerRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const menuStyle = ref<Record<string, string>>({})

const updatePosition = () => {
  if (!triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  const gap = 4

  const isBottom = props.placement.startsWith('bottom')
  const isEnd = props.placement.endsWith('end')

  const top = isBottom ? `${rect.bottom + gap}px` : undefined
  const bottom = !isBottom ? `${window.innerHeight - rect.top + gap}px` : undefined

  let left: string | undefined
  let right: string | undefined

  if (isEnd) {
    right = `${window.innerWidth - rect.right}px`
  } else {
    left = `${rect.left}px`
  }

  menuStyle.value = {
    position: 'fixed',
    top: top || 'auto',
    bottom: bottom || 'auto',
    left: left || 'auto',
    right: right || 'auto',
    minWidth: props.minWidth,
    zIndex: 'var(--z-popover, 70)'
  }
}

const toggleOpen = () => {
  if (props.disabled) return
  if (!isOpen.value) {
    updatePosition()
    isOpen.value = true
    nextTick(() => {
      updatePosition()
    })
  } else {
    isOpen.value = false
  }
}

const handleItemClick = (item: DropdownItem) => {
  if (item.disabled) return
  item.onClick?.()
  emit('select', item)
  isOpen.value = false
}

const handleClickOutside = (event: MouseEvent) => {
  const target = event.target as Node
  const inTrigger = triggerRef.value ? triggerRef.value.contains(target) : false
  const inMenu = menuRef.value ? menuRef.value.contains(target) : false
  if (!inTrigger && !inMenu) {
    isOpen.value = false
  }
}

const handleKeyDown = (event: KeyboardEvent) => {
  if (!isOpen.value) return
  if (event.key === 'Escape') {
    isOpen.value = false
  }
}

const handleScrollOrResize = () => {
  if (isOpen.value) {
    updatePosition()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeyDown)
  window.addEventListener('scroll', handleScrollOrResize, true)
  window.addEventListener('resize', handleScrollOrResize)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('scroll', handleScrollOrResize, true)
  window.removeEventListener('resize', handleScrollOrResize)
})
</script>

<template>
  <div class="m3-dropdown" ref="triggerRef">
    <slot name="trigger" :toggle="toggleOpen" :is-open="isOpen">
      <button
        type="button"
        class="m3-dropdown-trigger-btn md-state-layer"
        :class="{ 'is-active': isOpen }"
        :disabled="disabled"
        title="更多操作"
        aria-label="更多操作"
        @click.stop="toggleOpen"
      >
        <MoreHorizontal :size="16" />
      </button>
    </slot>

    <Teleport to="body">
      <Transition name="m3-menu-pop">
        <div
          v-if="isOpen"
          ref="menuRef"
          class="m3-dropdown-menu"
          :style="menuStyle"
          @click.stop
        >
          <slot :close="() => (isOpen = false)">
            <template v-for="(item, idx) in items" :key="item.key || idx">
              <button
                type="button"
                class="m3-dropdown-item md-state-layer"
                :class="{
                  'is-disabled': item.disabled,
                  'is-danger': item.danger
                }"
                :disabled="item.disabled"
                @click="handleItemClick(item)"
              >
                <component v-if="item.icon" :is="item.icon" :size="14" class="item-icon" />
                <span class="item-label">{{ item.label }}</span>
              </button>
            </template>
          </slot>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.m3-dropdown {
  position: relative;
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
}

.m3-dropdown-trigger-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--md-sys-shape-corner-small, 8px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  background-color: transparent;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  padding: 0;
  outline: none;
  transition: all var(--md-sys-motion-duration-short2) var(--md-easing-emphasized);
}

.m3-dropdown-trigger-btn:hover:not(:disabled) {
  background-color: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
  border-color: var(--md-sys-color-outline-variant);
}

.m3-dropdown-trigger-btn.is-active {
  background-color: var(--md-sys-color-surface-container-highest);
  color: var(--md-sys-color-primary);
  border-color: var(--md-sys-color-outline-variant);
}

.m3-dropdown-trigger-btn:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

.m3-dropdown-menu {
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-small, 8px);
  padding: 4px;
  box-shadow: var(--md-sys-elevation-level2);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.m3-dropdown-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--md-sys-color-on-surface);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  outline: none;
  transition: background-color var(--md-sys-motion-duration-short2) var(--md-easing-emphasized);
  white-space: nowrap;
}

.m3-dropdown-item:hover:not(:disabled) {
  background-color: var(--md-sys-color-surface-container-high);
}

.m3-dropdown-item.is-danger {
  color: var(--md-sys-color-error);
}

.m3-dropdown-item.is-danger:hover:not(:disabled) {
  background-color: color-mix(in srgb, var(--md-sys-color-error) 10%, transparent);
}

.m3-dropdown-item:disabled {
  opacity: 0.38;
  cursor: not-allowed;
}

.item-icon {
  flex-shrink: 0;
  color: currentColor;
}

.item-label {
  flex: 1;
}

/* 动效 */
.m3-menu-pop-enter-active,
.m3-menu-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.m3-menu-pop-enter-from,
.m3-menu-pop-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
