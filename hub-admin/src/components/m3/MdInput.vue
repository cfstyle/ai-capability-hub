<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { X } from 'lucide-vue-next'

export type InputSize = 'sm' | 'md'

const props = withDefaults(
  defineProps<{
    modelValue: string | number | null | undefined
    placeholder?: string
    type?: string
    size?: InputSize
    disabled?: boolean
    readonly?: boolean
    clearable?: boolean
    id?: string
    name?: string
    maxlength?: number
  }>(),
  {
    modelValue: '',
    placeholder: '',
    type: 'text',
    size: 'sm',
    disabled: false,
    readonly: false,
    clearable: false
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'input', value: string, event: Event): void
  (e: 'change', value: string, event: Event): void
  (e: 'clear'): void
  (e: 'focus', event: FocusEvent): void
  (e: 'blur', event: FocusEvent): void
  (e: 'keydown', event: KeyboardEvent): void
}>()

const isFocused = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

const showClear = computed(() => {
  return (
    props.clearable &&
    !props.disabled &&
    !props.readonly &&
    props.modelValue !== '' &&
    props.modelValue !== null &&
    props.modelValue !== undefined
  )
})

const handleInput = (event: Event) => {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', target.value)
  emit('input', target.value, event)
}

const handleChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  emit('change', target.value, event)
}

const handleClear = () => {
  emit('update:modelValue', '')
  emit('clear')
  nextTick(() => {
    inputRef.value?.focus()
  })
}

const handleFocus = (event: FocusEvent) => {
  isFocused.value = true
  emit('focus', event)
}

const handleBlur = (event: FocusEvent) => {
  isFocused.value = false
  emit('blur', event)
}

defineExpose({
  focus: () => inputRef.value?.focus(),
  blur: () => inputRef.value?.blur(),
  inputRef
})
</script>

<template>
  <div
    :class="[
      'm3-input',
      `m3-input--${size}`,
      {
        'is-focused': isFocused,
        'is-disabled': disabled,
        'is-readonly': readonly
      }
    ]"
  >
    <div v-if="$slots.prefix" class="m3-input__prefix">
      <slot name="prefix" />
    </div>

    <input
      :id="id"
      ref="inputRef"
      :type="type"
      :name="name"
      :value="modelValue ?? ''"
      :placeholder="placeholder"
      :disabled="disabled"
      :readonly="readonly"
      :maxlength="maxlength"
      class="m3-input__inner"
      @input="handleInput"
      @change="handleChange"
      @focus="handleFocus"
      @blur="handleBlur"
      @keydown="$emit('keydown', $event)"
    />

    <button
      v-if="showClear"
      type="button"
      class="m3-input__clear"
      tabindex="-1"
      title="清空"
      aria-label="清空输入"
      @click.stop="handleClear"
    >
      <X :size="size === 'sm' ? 14 : 16" />
    </button>

    <div v-if="$slots.suffix" class="m3-input__suffix">
      <slot name="suffix" />
    </div>
  </div>
</template>

<style scoped>
.m3-input {
  display: inline-flex;
  align-items: center;
  position: relative;
  box-sizing: border-box;
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-medium, 8px);
  color: var(--md-sys-color-on-surface);
  transition: all var(--md-sys-motion-duration-short2, 0.2s) var(--md-easing-emphasized, cubic-bezier(0.2, 0, 0, 1));
  width: 100%;
}

.m3-input:hover:not(.is-disabled):not(.is-focused) {
  background-color: var(--md-sys-color-surface-container-low);
  border-color: var(--md-sys-color-outline);
}

.m3-input.is-focused {
  border-color: var(--md-sys-color-primary);
  box-shadow: 0 0 0 0.5px var(--md-sys-color-primary);
  background-color: var(--md-sys-color-surface-container-lowest);
}

.m3-input.is-disabled {
  opacity: 0.38;
  cursor: not-allowed;
  background-color: var(--md-sys-color-surface-container);
}

/* 尺寸变体: sm (后台管理统一 36px 规范) */
.m3-input--sm {
  height: 36px;
  padding: 0 10px;
  font-size: var(--md-type-body-size, 13px);
  gap: 6px;
}

/* 尺寸变体: md (常规高度 40px) */
.m3-input--md {
  height: 40px;
  padding: 0 14px;
  font-size: var(--md-type-body-size, 14px);
  gap: 8px;
}

.m3-input__prefix,
.m3-input__suffix {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  color: var(--md-sys-color-on-surface-variant);
}

.m3-input__inner {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: var(--md-sys-color-on-surface);
  font-family: inherit;
  font-size: inherit;
  line-height: normal;
  padding: 0;
  margin: 0;
}

.m3-input__inner::placeholder {
  color: var(--md-sys-color-on-surface-variant);
  opacity: 0.7;
}

.m3-input__inner:disabled {
  cursor: not-allowed;
}

.m3-input__clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  outline: none;
  background: transparent;
  padding: 2px;
  margin: 0;
  color: var(--md-sys-color-on-surface-variant);
  cursor: pointer;
  border-radius: 50%;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.m3-input__clear:hover {
  color: var(--md-sys-color-on-surface);
  background-color: var(--md-sys-color-surface-container-high);
}
</style>
