<template>
  <div class="tool-debug-page">
    <div class="page-header">
      <div class="title-area">
        <h1 class="type-title-lg">工具在线调试台</h1>
        <p class="type-body-sm text-secondary">基于工具契约 Input Schema 动态组装参数并安全受控调用</p>
      </div>
    </div>

    <div class="debug-grid">
      <!-- 左侧：参数装配与控制 -->
      <MdCard variant="elevated" class="debug-card">
        <div class="card-top-row">
          <div class="title-with-icon">
            <Sliders :size="18" class="text-primary" />
            <h2 class="type-title-md">调用目标与入参装配</h2>
          </div>
          <!-- 模式切换 Segmented Buttons -->
          <div class="segmented-control">
            <button
              type="button"
              :class="['seg-btn', { 'is-active': inputMode === 'form' }]"
              @click="inputMode = 'form'"
            >
              动态表单
            </button>
            <button
              type="button"
              :class="['seg-btn', { 'is-active': inputMode === 'json' }]"
              @click="inputMode = 'json'"
            >
              JSON 模式
            </button>
          </div>
        </div>

        <!-- 目标选择区 (36px 等高内嵌前缀规范) -->
        <div class="target-selectors">
          <div class="selector-item">
            <MdSelect
              v-model="selectedServiceId"
              :options="serviceSelectOptions"
              prefix="目标服务："
              placeholder="请选择服务"
              size="sm"
              @change="handleServiceChange"
            />
          </div>

          <div class="selector-item">
            <MdSelect
              v-model="selectedToolName"
              :options="toolSelectOptions"
              prefix="目标工具："
              :disabled="!selectedServiceId"
              placeholder="请选择工具"
              size="sm"
              @change="handleToolChange"
            />
          </div>
        </div>

        <!-- 工具元数据与风险警示 -->
        <div v-if="currentTool" class="tool-meta-box">
          <div class="meta-header">
            <span class="mono-code">{{ currentTool.namespace_name || currentTool.name }}</span>
            <span :class="['risk-chip', `risk-${currentTool.risk_level.toLowerCase()}`]">
              风险: {{ currentTool.risk_level }}
            </span>
          </div>
          <p class="body-small text-secondary desc-text">
            {{ currentTool.description || '暂无业务描述' }}
          </p>
        </div>

        <!-- 受控操作确认防线 -->
        <div
          v-if="currentTool && (currentTool.risk_level === 'L2' || currentTool.risk_level === 'L3' || currentTool.requires_confirmation)"
          class="security-banner"
        >
          <div class="banner-top">
            <ShieldAlert :size="20" class="text-warning" />
            <div class="banner-title label-large">受控操作安全防线触发</div>
          </div>
          <p class="body-small text-secondary">
            该工具具有业务状态变更或副作用（{{ currentTool.risk_level }}）。网关受控机制要求明确人工授权方可执行。
          </p>
          <label class="confirm-checkbox label-medium">
            <input type="checkbox" v-model="safetyConfirmed" />
            <span>我已知晓该操作具备副作用 ({{ currentTool.risk_level }})，确认在当前环境下受控测试</span>
          </label>
        </div>

        <!-- 参数装配区域 -->
        <div class="params-area" v-if="currentTool">
          <div class="params-header">
            <span class="label-large">入参装配 (Arguments)</span>
            <button type="button" class="reset-btn text-primary body-small" @click="resetParams">
              <RotateCcw :size="14" />
              <span>重置为默认值</span>
            </button>
          </div>

          <!-- 1. 动态表单模式 -->
          <div v-if="inputMode === 'form'" class="form-mode">
            <div v-if="schemaProps.length > 0" class="schema-fields">
              <div v-for="prop in schemaProps" :key="prop.name" class="param-field">
                <div class="field-label-row">
                  <label class="label-medium" :for="`arg-${prop.name}`">
                    {{ prop.name }}
                    <span class="prop-type body-small">({{ prop.type }})</span>
                    <span v-if="prop.required" class="required-star">*</span>
                  </label>
                  <span v-if="prop.description" class="param-hint body-small text-secondary">{{ prop.description }}</span>
                </div>

                <!-- 枚举下拉 (36px 规范) -->
                <MdSelect
                  v-if="prop.enum"
                  :id="`arg-${prop.name}`"
                  v-model="formArgs[prop.name]"
                  :options="[
                    { label: '请选择枚举项', value: '' },
                    ...prop.enum.map((opt) => ({ label: String(opt), value: opt }))
                  ]"
                  placeholder="请选择枚举项"
                  size="sm"
                />

                <!-- 布尔开关 -->
                <div v-else-if="prop.type === 'boolean'" class="bool-switch-row">
                  <span class="body-medium">当前值: {{ formArgs[prop.name] ? 'True' : 'False' }}</span>
                  <MdSwitch
                    :model-value="!!formArgs[prop.name]"
                    @update:model-value="formArgs[prop.name] = $event"
                  />
                </div>

                <!-- 数字类型 (MdInput 36px 规范) -->
                <MdInput
                  v-else-if="prop.type === 'number' || prop.type === 'integer'"
                  :id="`arg-${prop.name}`"
                  v-model.number="formArgs[prop.name]"
                  type="number"
                  size="sm"
                  :placeholder="`请输入 ${prop.name}`"
                />

                <!-- 对象或数组 (JSON) -->
                <textarea
                  v-else-if="prop.type === 'object' || prop.type === 'array'"
                  :id="`arg-${prop.name}`"
                  v-model="formArgs[prop.name]"
                  class="m3-param-textarea"
                  rows="3"
                  placeholder="请输入合法的 JSON 字符串，例如 { 'item': 1 }"
                ></textarea>

                <!-- 默认字符串输入 (MdInput 36px 规范) -->
                <MdInput
                  v-else
                  :id="`arg-${prop.name}`"
                  v-model="formArgs[prop.name]"
                  type="text"
                  size="sm"
                  :placeholder="prop.description || `请输入 ${prop.name}`"
                />
              </div>
            </div>
            <div v-else class="empty-params text-secondary body-medium">
              该工具无需入参或未定义具体参数属性
            </div>
          </div>

          <!-- 2. JSON 模式 -->
          <div v-else class="json-mode">
            <textarea
              v-model="rawJsonArgs"
              class="m3-json-editor"
              rows="12"
              placeholder="{ &quot;key&quot;: &quot;value&quot; }"
            ></textarea>
          </div>

          <!-- 执行调用按钮 -->
          <div class="execute-actions">
            <MdButton
              variant="tonal"
              class="execute-btn"
              :disabled="isExecuteDisabled || calling"
              @click="handleExecute"
            >
              <PlayCircle :size="18" />
              <span v-if="!calling">发起受控测试调用 (tools/call)</span>
              <span v-else>正在握手调用...</span>
            </MdButton>
          </div>
        </div>

        <div v-else class="unselected-box text-secondary">
          <Terminal :size="36" class="text-secondary mb-2" />
          <p class="body-medium">请在上方面板选择目标 MCP Server 和 Tool 展开调试</p>
        </div>
      </MdCard>

      <!-- 右侧：调试响应反馈 -->
      <MdCard variant="elevated" class="result-card">
        <div class="card-top-row">
          <div class="title-with-icon">
            <Terminal :size="18" class="text-secondary" />
            <h2 class="type-title-md">调试响应反馈</h2>
          </div>
          <div v-if="callResult && !calling" class="response-tags" role="status">
            <span :class="['chip-pill', callResult.status === 'success' ? 'chip-active' : 'chip-error']">
              <Check v-if="callResult.status === 'success'" :size="14" aria-hidden="true" />
              <AlertTriangle v-else :size="14" aria-hidden="true" />
              {{ responseStatusLabels[callResult.status] }}
            </span>
            <span class="chip-pill chip-inactive">{{ callResult.duration_ms }} ms</span>
          </div>
        </div>

        <div v-if="calling" class="calling-state" role="status">
          <div class="spinner" aria-hidden="true"></div>
          <p class="body-medium">正在执行工具调用…</p>
        </div>

        <div v-else-if="callResult" class="result-body">
          <div v-if="callResult.error" class="error-banner" role="alert">
            <AlertTriangle :size="18" aria-hidden="true" />
            <div class="body-small">{{ callResult.error }}</div>
          </div>

          <div v-if="responseOutput || callResult.error" class="response-panel">
            <div class="response-toolbar">
              <span class="response-format">
                <FileJson v-if="responseOutput?.format === 'json'" :size="16" aria-hidden="true" />
                <Terminal v-else :size="16" aria-hidden="true" />
                {{ responseOutput?.format === 'json' ? 'JSON 输出' : responseOutput ? '文本输出' : '错误详情' }}
              </span>
              <button type="button" class="copy-btn md-state-layer" @click="copyResponse">
                <Check v-if="copied" :size="16" aria-hidden="true" />
                <Copy v-else :size="16" aria-hidden="true" />
                {{ copied ? '已复制' : '复制' }}
              </button>
            </div>
            <pre v-if="responseOutput" class="response-code" tabindex="0" aria-label="响应内容"><code><template v-for="(token, index) in responseTokens" :key="index"><span :class="token.kind ? 'json-' + token.kind : undefined">{{ token.text }}</span></template></code></pre>
          </div>
          <p v-else class="response-empty body-small">调用未返回内容</p>
        </div>

        <div v-else class="empty-state text-secondary">
          <FileJson :size="36" aria-hidden="true" />
          <p class="body-medium">执行工具后查看响应</p>
        </div>
      </MdCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  PlayCircle,
  Sliders,
  Terminal,
  ShieldAlert,
  RotateCcw,
  Copy,
  Check,
  AlertTriangle,
  FileJson
} from 'lucide-vue-next'
import { listServices } from '@/api/server'
import { listTools, testTool } from '@/api/tool'
import type { RegisteredService, RegisteredTool, ToolTestResponse } from '@/api/types'
import { MdCard, MdButton, MdSwitch, MdSelect, MdInput, type SelectOption } from '@/components/m3'
import { useToast } from '@/composables/useToast'
import { formatResponse, responseCodeTokens } from './responseFormat'

const route = useRoute()
const toast = useToast()

const services = ref<RegisteredService[]>([])
const allTools = ref<RegisteredTool[]>([])

const selectedServiceId = ref<string>('')
const selectedToolName = ref<string>('')
const inputMode = ref<'form' | 'json'>('form')

const formArgs = reactive<Record<string, any>>({})
const rawJsonArgs = ref<string>('{}')
const safetyConfirmed = ref<boolean>(false)

const calling = ref<boolean>(false)
const callResult = ref<ToolTestResponse | null>(null)
const copied = ref(false)

const serviceSelectOptions = computed<SelectOption[]>(() => [
  { label: '请选择服务', value: '' },
  ...services.value.map((s) => ({
    label: `${s.name} (${s.id})`,
    value: s.id,
  })),
])

const serviceTools = computed(() => {
  if (!selectedServiceId.value) return []
  return allTools.value.filter((t) => t.service_id === selectedServiceId.value)
})

const toolSelectOptions = computed<SelectOption[]>(() => [
  { label: '请选择工具', value: '' },
  ...serviceTools.value.map((t) => ({
    label: t.name,
    value: t.name,
  })),
])

const currentTool = computed(() => {
  if (!selectedServiceId.value || !selectedToolName.value) return null
  return serviceTools.value.find((t) => t.name === selectedToolName.value) || null
})

interface ParamSchemaItem {
  name: string
  type: string
  description?: string
  enum?: string[] | null
  required: boolean
}

const schemaProps = computed<ParamSchemaItem[]>(() => {
  if (!currentTool.value?.input_schema) return []
  const schema = currentTool.value.input_schema as {
    properties?: Record<string, { type?: string; description?: string; enum?: string[] }>
    required?: string[]
  }
  const props = schema.properties || {}
  const reqList: string[] = schema.required || []

  return Object.keys(props).map((k) => ({
    name: k,
    type: props[k].type || 'string',
    description: props[k].description || '',
    enum: props[k].enum || null,
    required: reqList.includes(k),
  }))
})

const isExecuteDisabled = computed(() => {
  if (!currentTool.value) return true
  if (
    (currentTool.value.risk_level === 'L2' ||
      currentTool.value.risk_level === 'L3' ||
      currentTool.value.requires_confirmation) &&
    !safetyConfirmed.value
  ) {
    return true
  }
  return false
})

const responseStatusLabels = {
  success: '调用成功',
  tool_error: '工具错误',
  exception: '调用异常',
}

const responseOutput = computed(() => formatResponse(callResult.value?.result))
const responseTokens = computed(() => {
  const output = responseOutput.value
  return output ? responseCodeTokens(output.text, output.format) : []
})

function handleServiceChange() {
  selectedToolName.value = ''
  callResult.value = null
  resetParams()
}

function handleToolChange() {
  callResult.value = null
  safetyConfirmed.value = false
  resetParams()
}

function resetParams() {
  Object.keys(formArgs).forEach((k) => delete formArgs[k])
  schemaProps.value.forEach((p) => {
    if (p.type === 'boolean') formArgs[p.name] = false
    else if (p.type === 'number' || p.type === 'integer') formArgs[p.name] = 0
    else formArgs[p.name] = ''
  })
  rawJsonArgs.value = JSON.stringify(formArgs, null, 2)
}

async function handleExecute() {
  if (!currentTool.value) return

  let payloadArgs: Record<string, unknown> = {}
  if (inputMode.value === 'json') {
    try {
      payloadArgs = JSON.parse(rawJsonArgs.value)
    } catch {
      toast.error('JSON 语法错误，请检查入参')
      return
    }
  } else {
    schemaProps.value.forEach((p) => {
      const val = formArgs[p.name]
      if (p.type === 'object' || p.type === 'array') {
        if (typeof val === 'string' && val.trim()) {
          try {
            payloadArgs[p.name] = JSON.parse(val)
          } catch {
            payloadArgs[p.name] = val
          }
        } else {
          payloadArgs[p.name] = val
        }
      } else if (val !== undefined && val !== '') {
        payloadArgs[p.name] = val
      }
    })
  }

  copied.value = false
  calling.value = true
  const startTime = performance.now()
  const toolId = currentTool.value.id || `${currentTool.value.service_id}__${currentTool.value.name}`

  try {
    const res = await testTool(toolId, payloadArgs)
    callResult.value = res
    if (res.status !== 'success') toast.error(responseStatusLabels[res.status])
  } catch (err: unknown) {
    const duration = Math.round(performance.now() - startTime)
    const error = err as { response?: { data?: { detail?: string } }; message?: string }
    callResult.value = {
      tool_name: currentTool.value.name,
      service_id: currentTool.value.service_id,
      status: 'exception',
      duration_ms: duration,
      error: error.response?.data?.detail || error.message || '后端测试接口未响应或执行失败',
    }
    toast.error('调用发生异常')
  } finally {
    calling.value = false
  }
}

async function copyResponse() {
  const text = responseOutput.value?.text ?? callResult.value?.error
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    toast.error('复制失败，请手动选中内容复制')
  }
}

async function init() {
  try {
    const [svcs, tls] = await Promise.all([
      listServices(undefined, { silent: true }),
      listTools(),
    ])
    services.value = svcs
    allTools.value = tls

    const qService = route.query.service_id as string
    const qTool = route.query.tool_name as string
    if (qService) {
      selectedServiceId.value = qService
      if (qTool) {
        selectedToolName.value = qTool
        resetParams()
      }
    }
  } catch (err: unknown) {
    const error = err as { message?: string }
    toast.error(`加载配置失败: ${error.message || '异常'}`)
  }
}

onMounted(() => {
  init()
})
</script>

<style scoped>
.tool-debug-page {
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

.text-error {
  color: var(--md-sys-color-error);
}

.text-warning {
  color: #b26a00;
}

.debug-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 20px;
}

@media (max-width: 1024px) {
  .debug-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

.debug-card,
.result-card {
  padding: 24px;
  border-radius: var(--md-sys-shape-corner-large, 24px);
  min-height: 600px;
  display: flex;
  flex-direction: column;
}

.card-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.title-with-icon {
  display: flex;
  align-items: center;
  gap: 10px;
}

.segmented-control {
  display: flex;
  background-color: var(--md-sys-color-surface-container-highest);
  padding: 3px;
  border-radius: var(--md-sys-shape-corner-full);
}

.seg-btn {
  padding: 4px 12px;
  border-radius: var(--md-sys-shape-corner-full);
  font-size: 12px;
  font-weight: 500;
  color: var(--md-sys-color-on-surface-variant);
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all var(--md-sys-motion-duration-short2) var(--md-sys-motion-easing-standard);
}

.seg-btn.is-active {
  background-color: var(--md-sys-color-surface);
  color: var(--md-sys-color-primary);
  box-shadow: var(--md-sys-elevation-level1);
  font-weight: 600;
}

.target-selectors {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.selector-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.m3-native-select {
  height: 42px;
  padding: 0 12px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  background-color: var(--md-sys-color-surface-container-highest);
  border: 1px solid var(--md-sys-color-outline-variant);
  color: var(--md-sys-color-on-surface);
  font-family: inherit;
  font-size: 14px;
  outline: none;
}

.m3-native-select:focus {
  border-color: var(--md-sys-color-primary);
}

.tool-meta-box {
  padding: 12px 16px;
  border-radius: var(--md-sys-shape-corner-medium, 14px);
  background-color: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  margin-bottom: 16px;
}

.meta-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.desc-text {
  line-height: 1.4;
}

.security-banner {
  padding: 14px 16px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  background-color: color-mix(in srgb, #f59e0b 10%, var(--md-sys-color-surface));
  border: 1px solid color-mix(in srgb, #f59e0b 35%, transparent);
  color: var(--md-sys-color-on-surface);
  margin-bottom: 16px;
}

.banner-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.banner-title {
  color: #b45309;
  font-weight: 700;
}

.confirm-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  cursor: pointer;
  font-size: 13px;
}

.params-area {
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
}

.params-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.reset-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-weight: 500;
}

.schema-fields {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 380px;
  overflow-y: auto;
  padding-right: 4px;
}

.param-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.prop-type {
  color: var(--md-sys-color-primary);
  margin-left: 4px;
}

.required-star {
  color: var(--md-sys-color-error);
}

.param-hint {
  font-size: 11px;
}

.m3-param-input,
.m3-param-textarea,
.m3-json-editor {
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--md-sys-shape-corner-medium, 8px);
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  color: var(--md-sys-color-on-surface);
  font-family: inherit;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
  transition: all 0.2s ease;
}

.m3-param-input:focus,
.m3-param-textarea:focus,
.m3-json-editor:focus {
  border-color: var(--md-sys-color-primary);
  box-shadow: 0 0 0 0.5px var(--md-sys-color-primary);
}

.m3-json-editor {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 13px;
  line-height: 1.45;
}

.bool-switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background-color: var(--md-sys-color-surface-container-highest);
  border-radius: var(--md-sys-shape-corner-medium, 12px);
}

.execute-actions {
  margin-top: auto;
  padding-top: 16px;
}

.execute-btn {
  width: 100%;
  height: 48px;
  font-size: 15px;
}

.unselected-box,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
  padding: 40px 0;
}

.result-card {
  min-width: 0;
  min-height: min(600px, 72vh);
}

.result-card .card-top-row {
  flex-wrap: wrap;
  gap: 12px;
}

.response-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.response-tags .chip-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.copy-btn {
  display: inline-flex;
  min-height: 44px;
  min-width: 74px;
  padding: 0 10px;
  gap: 6px;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: var(--md-sys-shape-corner-small);
  background: transparent;
  color: var(--md-sys-color-on-surface);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

@media (max-width: 1024px) {
  .result-card {
    min-height: 340px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation: none;
  }
}

.calling-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 16px;
  color: var(--md-sys-color-primary);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--md-sys-color-primary-container);
  border-top-color: var(--md-sys-color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.result-body {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.error-banner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--md-sys-shape-corner-medium);
  background-color: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
  overflow-wrap: anywhere;
}

.error-banner svg {
  flex: none;
}

.response-panel {
  min-width: 0;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-medium);
  background: var(--md-sys-color-surface-container-low);
}

.response-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 8px 0 14px;
}

.response-format {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--md-sys-color-on-surface-variant);
  font-size: 13px;
  font-weight: 600;
}

.response-code {
  margin: 0;
  padding: 16px;
  max-height: min(520px, 62vh);
  overflow: auto;
  overscroll-behavior: contain;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 0 0 var(--md-sys-shape-corner-medium) var(--md-sys-shape-corner-medium);
  background: var(--md-sys-color-surface-container-lowest);
  color: var(--md-sys-color-on-surface);
  font-family: 'JetBrains Mono', Consolas, 'Microsoft YaHei UI', monospace;
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  tab-size: 2;
}

.response-code code {
  font: inherit;
}

.json-key {
  color: var(--md-sys-color-primary);
  font-weight: 600;
}

.json-string {
  color: var(--md-sys-color-tertiary);
}

.json-literal {
  color: var(--md-sys-color-secondary);
  font-weight: 600;
}

.response-empty {
  margin: 0;
  padding: 16px;
  border: 1px dashed var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-medium);
  color: var(--md-sys-color-on-surface-variant);
}

.chip-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--md-sys-shape-corner-full);
  font-size: 12px;
  font-weight: 600;
}

.chip-active {
  background-color: color-mix(in srgb, #198754 12%, var(--md-sys-color-surface));
  color: color-mix(in srgb, var(--md-sys-color-on-surface) 65%, #198754);
  border: 1px solid color-mix(in srgb, #198754 25%, transparent);
}

.chip-inactive {
  background-color: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.chip-error {
  background-color: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.risk-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--md-sys-shape-corner-small, 6px);
  font-size: 11px;
  font-weight: 700;
}

.risk-l0 {
  background-color: color-mix(in srgb, #198754 12%, var(--md-sys-color-surface));
  color: #198754;
  border: 1px solid color-mix(in srgb, #198754 25%, transparent);
}

.risk-l1 {
  background-color: color-mix(in srgb, #f59e0b 12%, var(--md-sys-color-surface));
  color: #b45309;
  border: 1px solid color-mix(in srgb, #f59e0b 25%, transparent);
}

.risk-l2 {
  background-color: color-mix(in srgb, #ea580c 14%, var(--md-sys-color-surface));
  color: #c2410c;
  border: 1px solid color-mix(in srgb, #ea580c 25%, transparent);
}

.risk-l3 {
  background-color: var(--md-sys-color-error-container);
  color: var(--md-sys-color-on-error-container);
  border: 1px solid var(--md-sys-color-outline-variant);
}
</style>
