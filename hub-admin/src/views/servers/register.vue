<template>
  <div class="register-page">
    <!-- 顶部返回条 -->
    <div class="page-header">
      <div class="header-left">
        <button
          type="button"
          class="back-btn md-state-layer"
          title="返回服务列表"
          @click="$router.push('/servers/list')"
        >
          <ArrowLeft :size="20" />
        </button>
        <div>
          <h1 class="type-title-lg">注册远程 MCP Server</h1>
          <p class="type-body-sm text-secondary">向 Hub Gateway 录入并挂载新的 MCP Streamable HTTP 节点</p>
        </div>
      </div>
      <div class="header-right">
        <MdButton variant="tonal" size="sm" @click="$router.push('/admin/servers/publish')">
          <UploadCloud :size="16" />
          <span>上传 ZIP 插件包发布</span>
        </MdButton>
      </div>
    </div>

    <!-- 注册表单卡片 -->
    <MdCard variant="elevated" class="form-card">
      <div class="card-intro">
        <div class="intro-icon bg-primary-container text-on-primary-container">
          <Radio :size="24" />
        </div>
        <div class="intro-text">
          <h2 class="type-title-md">服务基本信息与连接契约</h2>
          <p class="type-body-sm text-secondary">
            注册提交后，Hub Core 控制面将自动向该端点发起网络握手探针，并通过 <code class="mono-code">tools/list</code> 提取其对外开放的全部工具声明与 JSON Schema。
          </p>
        </div>
      </div>

      <form class="m3-register-form" @submit.prevent="handleSubmit">
        <div class="form-field">
          <label class="label-medium" for="service_id">
            服务唯一标识 (Service ID) <span class="required-star">*</span>
          </label>
          <MdInput
            id="service_id"
            v-model="form.service_id"
            size="sm"
            placeholder="例如: message, order, crm (作为命名空间前缀)"
          />
          <span class="field-hint type-meta text-secondary">小写字母开头，仅允许小写字母、数字、下划线与连字符，2-64 字符</span>
        </div>

        <div class="form-field">
          <label class="label-medium" for="name">
            服务显示名称 <span class="required-star">*</span>
          </label>
          <MdInput
            id="name"
            v-model="form.name"
            size="sm"
            placeholder="例如: 企业消息通知 MCP Server"
          />
        </div>

        <div class="form-field">
          <label class="label-medium" for="endpoint_url">
            MCP 服务端点 (Streamable HTTP URL) <span class="required-star">*</span>
          </label>
          <MdInput
            id="endpoint_url"
            v-model="form.endpoint_url"
            type="url"
            size="sm"
            placeholder="例如: http://message-mcp:8082/mcp 或 http://127.0.0.1:8082/mcp"
          />
          <span class="field-hint type-meta text-secondary">必须提供能够支持 Streamable HTTP 协议的端点地址</span>
        </div>

        <div class="form-field">
          <label class="label-medium" for="owner">维护人员 / 团队</label>
          <MdInput
            id="owner"
            v-model="form.owner"
            size="sm"
            placeholder="例如: ai-platform-team / 张三"
          />
        </div>

        <div class="form-field">
          <label class="label-medium" for="description">业务能力描述</label>
          <textarea
            id="description"
            v-model="form.description"
            class="m3-form-textarea"
            rows="3"
            placeholder="简述该服务所提供的业务功能、工具边界及使用场景"
          ></textarea>
        </div>

        <div class="form-actions">
          <MdButton
            type="submit"
            variant="tonal"
            :disabled="submitting"
            class="submit-btn"
          >
            <span v-if="!submitting">探测并完成注册</span>
            <span v-else>正在建立连接并发现工具...</span>
          </MdButton>
          <MdButton variant="text" @click="$router.push('/servers/list')">
            取消
          </MdButton>
        </div>
      </form>
    </MdCard>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Radio, UploadCloud } from 'lucide-vue-next'
import { registerService } from '@/api/server'
import { MdCard, MdButton, MdInput } from '@/components/m3'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const toast = useToast()
const submitting = ref(false)

const form = reactive({
  service_id: '',
  name: '',
  endpoint_url: '',
  owner: '',
  description: '',
})

async function handleSubmit() {
  const sid = form.service_id.trim()
  const name = form.name.trim()
  const url = form.endpoint_url.trim()

  if (!sid || !name || !url) {
    toast.warning('请补全必要字段（标识、名称与端点地址）')
    return
  }

  const idPattern = /^[a-z][a-z0-9_-]{1,62}$/
  if (!idPattern.test(sid)) {
    toast.warning('服务标识格式不合规：必须小写字母开头，仅含小写字母、数字、下划线或连字符')
    return
  }

  submitting.value = true
  try {
    const created = await registerService({
      service_id: sid,
      name,
      endpoint_url: url,
      owner: form.owner.trim(),
      description: form.description.trim(),
    })
    toast.success(`MCP 服务 "${created.name}" 注册并探测成功！`)
    router.push(`/servers/${created.id}`)
  } catch (err: unknown) {
    const error = err as { response?: { data?: { detail?: string } }; message?: string }
    const msg = error.response?.data?.detail || error.message || '网络连接超时'
    toast.error(`服务注册失败: ${msg}`)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.register-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--md-sys-shape-corner-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--md-sys-color-on-surface-variant);
  background: var(--md-sys-color-surface-container);
  border: 1px solid var(--md-sys-color-outline-variant);
  cursor: pointer;
  transition: color var(--md-sys-motion-duration-short2) var(--md-sys-motion-easing-standard);
}

.back-btn:hover {
  color: var(--md-sys-color-on-surface);
  background: var(--md-sys-color-surface-container-high);
}

.text-secondary {
  color: var(--md-sys-color-on-surface-variant);
}

.form-card {
  max-width: 800px;
  padding: 32px;
  border-radius: var(--md-sys-shape-corner-medium, 16px);
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
}

.card-intro {
  display: flex;
  gap: 16px;
  padding-bottom: 24px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.intro-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--md-sys-shape-corner-medium, 12px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.bg-primary-container {
  background-color: var(--md-sys-color-primary-container);
}
.text-on-primary-container {
  color: var(--md-sys-color-on-primary-container);
}

.intro-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.m3-register-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 600px;
}

.required-star {
  color: var(--md-sys-color-error);
}

.m3-form-textarea {
  width: 100%;
  max-width: 600px;
  padding: 10px 12px;
  background-color: var(--md-sys-color-surface-container-lowest);
  border: 1px solid var(--md-sys-color-outline-variant);
  border-radius: var(--md-sys-shape-corner-medium, 8px);
  color: var(--md-sys-color-on-surface);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  outline: none;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.m3-form-textarea:focus {
  border-color: var(--md-sys-color-primary);
  box-shadow: 0 0 0 0.5px var(--md-sys-color-primary);
}

.field-hint {
  color: var(--md-sys-color-outline);
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
}

.submit-btn {
  height: 44px;
  padding: 0 24px;
}
</style>
