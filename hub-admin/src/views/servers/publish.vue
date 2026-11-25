<template>
  <div class="publish-page">
    <!-- 顶部导航与操作栏 -->
    <div class="page-header">
      <div class="header-left">
        <button
          type="button"
          class="back-btn md-state-layer"
          title="返回服务列表"
          @click="$router.push('/admin/servers/list')"
        >
          <ArrowLeft :size="20" />
        </button>
        <div>
          <div class="title-row">
            <h1 class="type-title-lg">自助发布 MCP 插件</h1>
            <span class="badge-auto">零配置全自助</span>
          </div>
          <p class="type-body-sm text-secondary">
            上传符合规范的 Python MCP 插件包 (.zip)，由运行底座自动托管、存活探测并无缝挂载至 Gateway
          </p>
        </div>
      </div>

      <div class="header-actions">
        <MdButton variant="tonal" size="sm" :disabled="downloadingTemplate" @click="handleDownloadTemplate">
          <Download :size="16" />
          <span>{{ downloadingTemplate ? '下载中...' : '下载脚手架模板 (.zip)' }}</span>
        </MdButton>
        <MdButton variant="outlined" size="sm" @click="showGuideModal = true">
          <BookOpen :size="16" />
          <span>开发规范手册</span>
        </MdButton>
      </div>
    </div>

    <div class="publish-container">
      <!-- 步骤 1：文件上传与预检区域 -->
      <MdCard variant="elevated" class="section-card">
        <div class="card-title-bar">
          <div class="step-num">1</div>
          <div>
            <h2 class="type-title-md">上传插件发布包</h2>
            <p class="type-body-sm text-secondary">请选择包含 <code class="mono-code">manifest.json</code> 与 <code class="mono-code">server.py</code> 的标准 ZIP 压缩包</p>
          </div>
        </div>

        <div
          class="drop-zone"
          :class="{ 'is-dragover': isDragging, 'has-file': !!selectedFile, 'is-valid': inspectResult?.valid }"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleDrop"
          @click="triggerFileInput"
        >
          <input
            ref="fileInputRef"
            type="file"
            accept=".zip"
            class="hidden-file-input"
            @change="handleFileChange"
          />

          <div v-if="!selectedFile" class="drop-placeholder">
            <div class="upload-icon-circle">
              <UploadCloud :size="32" />
            </div>
            <p class="type-title-sm upload-main-text">点击或将 .zip 插件包拖拽至此处</p>
            <p class="type-body-xs text-secondary">单文件最大 50MB，基于统一运行底座 mcp-runner 运行</p>
          </div>

          <div v-else class="file-summary">
            <div class="file-icon bg-primary-container text-on-primary-container">
              <FileCheck :size="28" />
            </div>
            <div class="file-info">
              <div class="file-name-row">
                <span class="file-name type-title-sm">{{ selectedFile.name }}</span>
                <span class="file-size type-meta text-secondary">({{ formatFileSize(selectedFile.size) }})</span>
              </div>
              <p v-if="inspecting" class="type-meta text-primary is-inspecting">正在执行安全合规与代码语法预检...</p>
              <p v-else-if="inspectResult?.valid" class="type-meta text-success">
                预检通过：共 {{ inspectResult.file_count }} 个文件，检测到 {{ inspectResult.tools?.length || 0 }} 个能力工具声明
              </p>
              <p v-else-if="inspectError" class="type-meta text-error">
                校验未通过：{{ inspectError }}
              </p>
            </div>
            <button
              type="button"
              class="reselect-btn md-state-layer"
              title="重新选择"
              @click.stop="triggerFileInput"
            >
              更换文件
            </button>
          </div>
        </div>

        <!-- 快速提示横幅 -->
        <div class="guide-banner">
          <Sparkles :size="18" class="text-primary" />
          <span class="type-body-xs">
            <strong>AI Native 提示：</strong> 将脚手架模板解压后，配合内置的 <code class="mono-code">agent.md</code> 提示词直接发给 AI 助手，描述业务诉求即可自动生成生产就绪代码。
          </span>
        </div>
      </MdCard>

      <!-- 步骤 2：元数据确认与工具预览 -->
      <MdCard v-if="inspectResult?.valid" variant="elevated" class="section-card fade-in">
        <div class="card-title-bar">
          <div class="step-num">2</div>
          <div>
            <h2 class="type-title-md">确认服务信息与接入契约</h2>
            <p class="type-body-sm text-secondary">以下信息已根据插件 manifest.json 自动解析提取，可根据需要调整</p>
          </div>
        </div>

        <div class="metadata-grid">
          <div class="form-field">
            <label class="label-medium" for="pub_service_id">服务标识 (Service ID) <span class="required-star">*</span></label>
            <MdInput
              id="pub_service_id"
              v-model="publishForm.service_id"
              size="sm"
              placeholder="例如: order, crm"
            />
            <span class="field-hint type-meta text-secondary">小写字母开头，作为该服务下所有工具的命名空间前缀</span>
          </div>

          <div class="form-field">
            <label class="label-medium" for="pub_name">服务显示名称 <span class="required-star">*</span></label>
            <MdInput
              id="pub_name"
              v-model="publishForm.name"
              size="sm"
              placeholder="例如: 智能订单管理服务"
            />
          </div>

          <div class="form-field">
            <label class="label-medium" for="pub_owner">维护人员 / 团队</label>
            <MdInput
              id="pub_owner"
              v-model="publishForm.owner"
              size="sm"
              placeholder="例如: 商业智能部 / 张三"
            />
          </div>

          <div class="form-field">
            <label class="label-medium" for="pub_category">业务分类</label>
            <MdInput
              id="pub_category"
              v-model="publishForm.category"
              size="sm"
              placeholder="例如: 交易风控、资产管理、通用"
            />
          </div>

          <div class="form-field full-width">
            <label class="label-medium" for="pub_desc">能力描述</label>
            <textarea
              id="pub_desc"
              v-model="publishForm.description"
              class="m3-form-textarea"
              rows="2"
              placeholder="简要介绍该插件服务的功能边界"
            ></textarea>
          </div>
        </div>

        <!-- 工具声明预览 -->
        <div v-if="inspectResult.tools?.length" class="tools-preview-area">
          <h3 class="type-title-sm tools-title">
            <Wrench :size="16" />
            <span>声明的 MCP 工具清单 ({{ inspectResult.tools.length }})</span>
          </h3>
          <div class="tools-table-wrap">
            <table class="tools-table">
              <thead>
                <tr>
                  <th>工具名称</th>
                  <th>风险等级</th>
                  <th>功能说明</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in inspectResult.tools" :key="t.name">
                  <td class="mono-cell font-semibold">{{ t.name }}</td>
                  <td>
                    <span :class="['risk-badge', `risk-${(t.risk_level || 'L0').toLowerCase()}`]">
                      {{ t.risk_level || 'L0' }}
                    </span>
                  </td>
                  <td class="text-secondary">{{ t.description || '无详细说明' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 提交发布动作 -->
        <div class="publish-action-bar">
          <div class="action-summary type-body-sm text-secondary">
            点击发布后，系统将自动解压落地代码、自适应分配端口并执行健康探测，挂载入网关。
          </div>
          <MdButton
            variant="tonal"
            size="md"
            :disabled="publishing || inspecting"
            @click="handlePublish"
          >
            <Play v-if="!publishing" :size="18" />
            <RefreshCw v-else :size="18" class="is-spinning" />
            <span>{{ publishing ? '正在部署上线...' : '立即发布并上线' }}</span>
          </MdButton>
        </div>
      </MdCard>
    </div>

    <!-- 开发规范弹窗 -->
    <AdaptiveModal
      v-model="showGuideModal"
      title="业务 MCP 插件开发规范与发布手册"
      width="780px"
    >
      <div v-if="loadingGuide" class="guide-loading type-body-sm text-secondary">
        正在拉取最新规范文档...
      </div>
      <div v-else class="guide-content markdown-body">
        <pre class="guide-raw-text">{{ guideContent }}</pre>
      </div>
      <template #footer>
        <MdButton variant="tonal" @click="showGuideModal = false">关闭</MdButton>
      </template>
    </AdaptiveModal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  UploadCloud,
  Download,
  BookOpen,
  FileCheck,
  Sparkles,
  Wrench,
  Play,
  RefreshCw,
} from 'lucide-vue-next'
import MdCard from '@/components/m3/MdCard.vue'
import MdButton from '@/components/m3/MdButton.vue'
import MdInput from '@/components/m3/MdInput.vue'
import AdaptiveModal from '@/components/m3/AdaptiveModal.vue'
import { useToast } from '@/composables/useToast'
import {
  inspectPlugin,
  publishPlugin,
  downloadPluginTemplate,
  getDeveloperGuide,
  PluginInspectResult,
} from '@/api/server'

const router = useRouter()
const toast = useToast()

const isDragging = ref(false)
const selectedFile = ref<File | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

const inspecting = ref(false)
const inspectResult = ref<PluginInspectResult | null>(null)
const inspectError = ref('')

const publishing = ref(false)
const downloadingTemplate = ref(false)

const showGuideModal = ref(false)
const loadingGuide = ref(false)
const guideContent = ref('')

const publishForm = reactive({
  service_id: '',
  name: '',
  owner: '',
  category: '自研业务',
  description: '',
})

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function triggerFileInput() {
  fileInputRef.value?.click()
}

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    processFile(input.files[0])
  }
}

function handleDrop(event: DragEvent) {
  isDragging.value = false
  if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
    processFile(event.dataTransfer.files[0])
  }
}

async function processFile(file: File) {
  if (!file.name.toLowerCase().endsWith('.zip')) {
    toast.error('仅支持上传 .zip 格式的 MCP 插件压缩包')
    return
  }
  selectedFile.value = file
  inspectResult.value = null
  inspectError.value = ''
  inspecting.value = true

  try {
    const res = await inspectPlugin(file)
    inspectResult.value = res
    // 自动回填表单
    publishForm.service_id = res.service_id || ''
    publishForm.name = res.name || ''
    publishForm.owner = res.author || ''
    publishForm.description = res.description || ''
    toast.success(`插件包校验通过：${res.name} (含 ${res.tools?.length || 0} 个工具)`)
  } catch (err: any) {
    inspectError.value = err?.response?.data?.detail || err?.message || '插件包校验失败'
    toast.error(inspectError.value)
  } finally {
    inspecting.value = false
  }
}

async function handlePublish() {
  if (!selectedFile.value || !inspectResult.value) {
    toast.warning('请先上传并校验合规的插件发布包')
    return
  }
  if (!publishForm.service_id.trim()) {
    toast.warning('服务标识 (Service ID) 不能为空')
    return
  }

  publishing.value = true
  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('service_id', publishForm.service_id.trim())
  formData.append('name', publishForm.name.trim())
  formData.append('owner', publishForm.owner.trim())
  formData.append('category', publishForm.category.trim())
  formData.append('description', publishForm.description.trim())

  try {
    const res = await publishPlugin(formData)
    toast.success(`MCP 插件 [${res.name}] 发布成功并已接入网关！`)
    router.push(`/admin/servers/${res.id}`)
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.message || '发布上线失败'
    toast.error(`发布失败: ${detail}`)
  } finally {
    publishing.value = false
  }
}

async function handleDownloadTemplate() {
  downloadingTemplate.value = true
  try {
    const blob = await downloadPluginTemplate()
    const url = window.URL.createObjectURL(new Blob([blob], { type: 'application/zip' }))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'python-mcp-demo.zip')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    toast.success('脚手架模板包下载成功！')
  } catch (err: any) {
    toast.error('下载模板失败: ' + (err?.message || '网络异常'))
  } finally {
    downloadingTemplate.value = false
  }
}

onMounted(async () => {
  try {
    loadingGuide.value = true
    const res = await getDeveloperGuide()
    guideContent.value = res.content || '暂无内容'
  } catch {
    guideContent.value = '无法加载开发规范文档，请稍后重试。'
  } finally {
    loadingGuide.value = false
  }
})
</script>

<style scoped>
.publish-page {
  padding: 24px;
  max-width: 1040px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  background: transparent;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 50%;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--md-sys-color-on-surface);
  transition: all 0.2s ease;
}

.back-btn:hover {
  background: var(--md-sys-color-surface-container-high);
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.badge-auto {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.publish-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-card {
  padding: 24px;
  border-radius: 16px;
  background: var(--md-sys-color-surface-container-low);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.card-title-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
}

.step-num {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
}

/* 拖拽上传区 */
.drop-zone {
  border: 2px dashed var(--md-sys-color-outline);
  border-radius: 12px;
  padding: 36px 24px;
  text-align: center;
  cursor: pointer;
  background: var(--md-sys-color-surface);
  transition: all 0.2s ease;
  position: relative;
}

.drop-zone:hover,
.drop-zone.is-dragover {
  border-color: var(--md-sys-color-primary);
  background: var(--md-sys-color-surface-container-high);
}

.drop-zone.is-valid {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.04);
}

.hidden-file-input {
  display: none;
}

.drop-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.upload-icon-circle {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4px;
}

.upload-main-text {
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}

.file-summary {
  display: flex;
  align-items: center;
  gap: 16px;
  text-align: left;
}

.file-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.file-info {
  flex: 1;
}

.file-name-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.file-name {
  font-weight: 600;
  color: var(--md-sys-color-on-surface);
}

.reselect-btn {
  background: transparent;
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  color: var(--md-sys-color-primary);
}

.text-success {
  color: #10b981;
}

.text-error {
  color: var(--md-sys-color-error);
}

.guide-banner {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  background: var(--md-sys-color-surface-container);
  color: var(--md-sys-color-on-surface-variant);
}

.mono-code {
  font-family: monospace;
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 4px;
}

/* 表单网格 */
.metadata-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.full-width {
  grid-column: span 2;
}

.m3-form-textarea {
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--md-sys-color-outline);
  background: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface);
  font-family: inherit;
  font-size: 14px;
  resize: vertical;
}

.m3-form-textarea:focus {
  outline: none;
  border-color: var(--md-sys-color-primary);
}

/* 工具列表表格 */
.tools-preview-area {
  margin-bottom: 24px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  padding-top: 20px;
}

.tools-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
}

.tools-table-wrap {
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: 8px;
  overflow: hidden;
}

.tools-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.tools-table th {
  background: var(--md-sys-color-surface-container);
  padding: 10px 14px;
  text-align: left;
  font-weight: 600;
  color: var(--md-sys-color-on-surface-variant);
}

.tools-table td {
  padding: 10px 14px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
}

.risk-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 700;
}

.risk-l0 {
  background: #dcfce7;
  color: #15803d;
}

.risk-l1 {
  background: #e0f2fe;
  color: #0369a1;
}

.risk-l2 {
  background: #fef3c7;
  color: #b45309;
}

.risk-l3 {
  background: #fee2e2;
  color: #b91c1c;
}

.publish-action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  padding-top: 20px;
  gap: 16px;
  flex-wrap: wrap;
}

.guide-raw-text {
  white-space: pre-wrap;
  word-wrap: break-word;
  background: var(--md-sys-color-surface);
  padding: 16px;
  border-radius: 8px;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  max-height: 480px;
  overflow-y: auto;
}

.fade-in {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
