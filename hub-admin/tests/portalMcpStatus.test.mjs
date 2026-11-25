import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  buildPermissionRequestPayload,
  getMyMcpStatusClass,
  getMyMcpStatusLabel,
  selectedToolsRequireCredentials,
  validateCredentialFormForSelectedTools,
} from '../src/views/portal/mcpStatus.ts'

test('renders all four required portal credential and downstream states distinctly', () => {
  const saved = {
    requires_credentials: true,
    credential_status: 'saved',
    downstream_status: 'available',
    approved_tools: ['ticm__portfolio_summary'],
  }
  assert.equal(getMyMcpStatusLabel(saved), '已保存')
  assert.match(getMyMcpStatusClass(saved), /bg-primary-container/)

  const verified = {
    requires_credentials: true,
    credential_status: 'verified',
    downstream_status: 'available',
    approved_tools: ['ticm__portfolio_summary'],
  }
  assert.equal(getMyMcpStatusLabel(verified), '已验证')
  assert.match(getMyMcpStatusClass(verified), /bg-success-container/)

  const invalid = {
    requires_credentials: true,
    credential_status: 'invalid',
    downstream_status: 'available',
    approved_tools: ['ticm__portfolio_summary'],
  }
  assert.equal(getMyMcpStatusLabel(invalid), '登录失效')
  assert.match(getMyMcpStatusClass(invalid), /bg-error-container/)

  const downstreamUnavailable = {
    requires_credentials: true,
    credential_status: 'verified',
    downstream_status: 'unavailable',
    approved_tools: ['ticm__portfolio_summary'],
  }
  assert.equal(getMyMcpStatusLabel(downstreamUnavailable), '下游不可用')
  assert.match(getMyMcpStatusClass(downstreamUnavailable), /bg-error-container/)
})

test('apply modal hides password form and omits credentials when only non-credential tools are selected', () => {
  const ticmDetail = {
    id: 'ticm',
    credential_schema: {
      enabled: true,
      fields: [
        { field_name: 'username', label: 'TICM 用户名', required: true },
        { field_name: 'password', label: 'TICM 登录密码', required: true },
      ],
    },
    tools: [
      {
        id: 'ticm__approval_only_report',
        name: 'approval_only_report',
        namespace_name: 'ticm__approval_only_report',
        requires_credentials: false,
      },
      {
        id: 'ticm__portfolio_summary',
        name: 'portfolio_summary',
        namespace_name: 'ticm__portfolio_summary',
        requires_credentials: true,
      },
    ],
  }

  // 1. 只申请免凭据工具：不展示密码框、校验通过且不发送 credentials 字段
  const onlyNoCredSelected = new Set(['ticm__approval_only_report'])
  assert.equal(selectedToolsRequireCredentials(ticmDetail, onlyNoCredSelected), false)
  assert.deepEqual(
    validateCredentialFormForSelectedTools(ticmDetail, onlyNoCredSelected, false, false, {}),
    { valid: true },
  )
  const payloadNoCred = buildPermissionRequestPayload({
    userId: 'dev-user',
    userName: '张三',
    detail: ticmDetail,
    selectedToolIds: onlyNoCredSelected,
    reason: '申请免凭据审批报表',
    hasExistingBinding: false,
    showCustomCredInApply: false,
    credentialForm: {},
  })
  assert.equal('credentials' in payloadNoCred, false)
  assert.deepEqual(payloadNoCred.tool_ids, ['ticm__approval_only_report'])

  // 2. 勾选需凭据工具：展示密码框、校验必填并携带 credentials
  const withCredSelected = new Set(['ticm__approval_only_report', 'ticm__portfolio_summary'])
  assert.equal(selectedToolsRequireCredentials(ticmDetail, withCredSelected), true)
  const invalidCheck = validateCredentialFormForSelectedTools(ticmDetail, withCredSelected, false, false, { username: 'zhangsan' })
  assert.equal(invalidCheck.valid, false)
  assert.equal(invalidCheck.missingFieldLabel, 'TICM 登录密码')

  const payloadWithCred = buildPermissionRequestPayload({
    userId: 'dev-user',
    userName: '张三',
    detail: ticmDetail,
    selectedToolIds: withCredSelected,
    reason: '申请持仓查询',
    hasExistingBinding: false,
    showCustomCredInApply: false,
    credentialForm: { username: 'zhangsan', password: 'pwd_zhangsan_123' },
  })
  assert.deepEqual(payloadWithCred.credentials, { username: 'zhangsan', password: 'pwd_zhangsan_123' })
})
