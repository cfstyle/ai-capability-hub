"""Registry 数据模型

定义服务注册、工具注册相关的 Pydantic 模型和枚举。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, computed_field


class ServiceStatus(str, Enum):
    """服务状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    PENDING = "pending"


class ToolRiskLevel(str, Enum):
    """工具风险等级

    L0: 只读、无副作用（如查询天气）
    L1: 有限写入、可撤销（如创建草稿）
    L2: 不可撤销写入（如发送邮件、转账）
    L3: 系统级操作（如删除数据库、修改权限）
    """

    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class CredentialFieldType(str, Enum):
    """凭据字段类型"""
    TEXT = "text"
    PASSWORD = "password"


class CredentialFieldSchema(BaseModel):
    """单项凭据字段声明"""
    field_name: str = Field(..., description="字段标识，如 username, password")
    label: str = Field(..., description="显示名称，如 TICM 用户名, 登录密码")
    field_type: CredentialFieldType = Field(default=CredentialFieldType.TEXT, description="字段类型")
    required: bool = Field(default=True, description="是否必填")
    secret: bool = Field(default=False, description="是否为保密字段")
    description: str = Field(default="", description="输入提示说明")


class ServiceCredentialSchema(BaseModel):
    """服务凭据要求声明规范 (ADR-011)"""
    enabled: bool = Field(default=False, description="是否需要个人业务凭据绑定")
    auth_type: str = Field(default="username_password", description="认证类型")
    instructions: str = Field(default="", description="业务凭据配置引导说明")
    fields: List[CredentialFieldSchema] = Field(default_factory=list, description="凭据字段定义")
    help_text: str = Field(default="", description="业务凭据配置引导说明")


class RegisteredService(BaseModel):
    """已注册的 MCP 服务"""

    id: str = Field(..., description="服务唯一标识（用作命名空间前缀）")
    name: str = Field(..., description="服务显示名称")
    description: str = Field(default="", description="服务描述")
    endpoint_url: str = Field(..., description="MCP Streamable HTTP 地址")
    version: str = Field(default="0.0.0", description="服务版本")
    owner: str = Field(default="", description="服务负责人/团队")
    status: ServiceStatus = Field(default=ServiceStatus.PENDING, description="服务状态")
    category: str = Field(default="通用", description="业务分类标签")
    auth_mode: str = Field(default="platform_sso", description="认证模式")
    auth_label: str = Field(default="Hub 统一认证", description="认证方式显示标签")
    auth_guide: str = Field(
        default="调用具体业务能力时，由 Capability Hub 统一进行身份校验与权限换发",
        description="统一认证引导说明",
    )
    auth_entry_url: str = Field(default="", description="统一认证跳转入口地址")
    usage_examples: List[str] = Field(default_factory=list, description="适用场景与示例问法")
    credential_schema: Optional[ServiceCredentialSchema] = Field(
        default=None, description="个人业务凭据需求声明"
    )
    trusted_credential_recipient: bool = Field(
        default=False, description="是否为经管理员独立确认的可信凭据接收方"
    )
    trusted_credential_version: Optional[str] = Field(
        default=None, description="已确认可信的插件版本号"
    )
    trusted_credential_endpoint_url: Optional[str] = Field(
        default=None, description="已确认可信的下游端点地址"
    )
    trusted_confirmed_by: Optional[str] = Field(
        default=None, description="确认可信的管理员"
    )
    trusted_confirmed_at: Optional[datetime] = Field(
        default=None, description="确认可信时间"
    )
    downstream_status: str = Field(
        default="available", description="下游可达状态: available / unavailable"
    )
    downstream_error: Optional[str] = Field(
        default=None, description="最近一次下游不可用错误信息"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="注册时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="最后更新时间",
    )


class PermissionRequestStatus(str, Enum):
    """权限申请状态"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UserGrant(BaseModel):
    """用户工具授权记录"""

    id: str = Field(default="", description="授权记录 ID")
    user_id: str = Field(..., description="授权用户 ID/工号")
    tool_id: str = Field(..., description="授权的具体工具 ID")
    granted_by: str = Field(default="admin", description="审批/授权人")
    granted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="授权生效时间",
    )
    status: str = Field(default="active", description="状态")


class PermissionRequest(BaseModel):
    """用户功能权限申请单"""

    id: str = Field(..., description="申请单唯一编号")
    user_id: str = Field(..., description="申请人用户 ID/工号")
    user_name: str = Field(default="", description="申请人姓名")
    service_id: str = Field(..., description="目标服务 ID")
    service_name: str = Field(default="", description="服务显示名称")
    tool_ids: List[str] = Field(default_factory=list, description="申请开通的工具 ID 列表")
    tool_names: List[str] = Field(default_factory=list, description="工具显示名称列表")
    reason: str = Field(default="", description="申请用途/业务说明")
    has_credential_binding: bool = Field(default=False, description="是否已关联个人业务凭据")
    credential_summary: Optional[Dict[str, Any]] = Field(default=None, description="凭据非保密摘要")
    status: PermissionRequestStatus = Field(
        default=PermissionRequestStatus.PENDING,
        description="审批状态",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="申请提交时间",
    )
    reviewed_by: Optional[str] = Field(default=None, description="审批人")
    reviewed_at: Optional[datetime] = Field(default=None, description="审批时间")
    comment: Optional[str] = Field(default=None, description="审批批注/驳回原因")


class PermissionRequestCreate(BaseModel):
    """提交权限申请入参"""

    user_id: Optional[str] = Field(default="", description="申请人工号/用户标识 (以服务端验证为准)")
    user_name: str = Field(default="", description="申请人姓名")
    service_id: str = Field(..., description="服务 ID")
    tool_ids: List[str] = Field(..., min_length=1, description="申请的功能工具 ID 列表")
    reason: str = Field(..., min_length=2, description="申请说明/业务原因")
    credentials: Optional[Dict[str, Any]] = Field(default=None, description="可选携带初始业务凭据绑定")


class UserServiceBinding(BaseModel):
    """用户对特定 MCP 服务的个人业务凭据绑定状态"""

    id: str = Field(..., description="绑定记录唯一 ID")
    user_id: str = Field(..., description="用户 ID/工号")
    service_id: str = Field(..., description="MCP 服务 ID")
    credential_summary: Dict[str, Any] = Field(default_factory=dict, description="非敏感脱敏摘要")
    credential_version: int = Field(default=1, description="凭据版本号（更新密码自增）")
    status: str = Field(default="active", description="状态: active (已绑定), unbound (已解绑), invalid (验证失效)")
    validation_status: str = Field(default="saved", description="凭据验证状态: saved (已保存), verified (已验证), invalid (登录失效), unbound (已解绑)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserServiceBindingCreate(BaseModel):
    """用户提交或更新凭据入参"""

    service_id: str = Field(..., description="目标服务 ID")
    credentials: Dict[str, Any] = Field(..., description="个人凭据键值对，如 {'username': '...', 'password': '...'}")


class UserServiceBindingUpdate(BaseModel):
    """用户修改凭据入参"""

    credentials: Dict[str, Any] = Field(..., description="新凭据键值对")


class UserMcpDetail(BaseModel):
    """“我添加的 MCP”业务聚合详情模型"""

    service_id: str
    service_name: str
    category: str
    endpoint_url: str
    requires_credentials: bool
    credential_status: str  # "not_required", "saved", "verified", "invalid", "unbound", "missing"
    service_status: str = "active"
    downstream_status: str = "available"  # "available", "unavailable"
    downstream_error: Optional[str] = None
    credential_summary: Dict[str, Any]
    credential_version: int
    approved_tools: List[str]
    pending_tools: List[str]
    updated_at: Optional[datetime] = None


class PermissionRequestReview(BaseModel):
    """审核权限申请入参"""

    status: PermissionRequestStatus = Field(..., description="审核结论 (approved / rejected)")
    reviewer: str = Field(default="admin", description="审核人")
    comment: Optional[str] = Field(default=None, description="审核批注")


class RegisteredTool(BaseModel):
    """已注册的工具"""

    id: str = Field(default="", description="工具唯一 ID")
    service_id: str = Field(..., description="所属服务 ID")
    name: str = Field(..., description="工具原始名称")
    description: str = Field(default="", description="工具描述")
    input_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="工具输入 JSON Schema",
    )
    risk_level: ToolRiskLevel = Field(
        default=ToolRiskLevel.L0,
        description="风险等级",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="是否需要人工确认（L2+ 默认 True）",
    )
    requires_credentials: bool = Field(
        default=False,
        description="是否需要个人业务凭据绑定",
    )
    requires_credentials_explicit: Optional[bool] = Field(
        default=None,
        exclude=True,
        description="内部标记：上游或 manifest 是否显式声明了 requires_credentials",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="注册时间",
    )

    @computed_field
    @property
    def namespace_name(self) -> str:
        """命名空间化的工具名称: {service_id}__{tool_name}"""
        return f"{self.service_id}__{self.name}"


class ServiceRegistration(BaseModel):
    """服务注册请求（输入模型）"""

    endpoint_url: str = Field(..., description="MCP Streamable HTTP 地址")
    version: str = Field(default="1.0.0", description="服务版本")
    service_id: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_-]{1,62}$",
        description="服务唯一标识（小写字母开头，仅含小写字母、数字、下划线、连字符）",
    )
    name: str = Field(..., description="服务显示名称")
    description: str = Field(default="", description="服务描述")
    owner: str = Field(default="", description="服务负责人/团队")
    category: str = Field(default="通用", description="业务分类标签")
    auth_mode: str = Field(default="platform_sso", description="认证模式")
    auth_label: str = Field(default="Hub 统一认证", description="认证方式显示标签")
    auth_guide: str = Field(
        default="调用具体业务能力时，由 Capability Hub 统一进行身份校验与权限换发",
        description="统一认证引导说明",
    )
    auth_entry_url: str = Field(default="", description="统一认证跳转入口地址")
    usage_examples: List[str] = Field(default_factory=list, description="适用场景与示例问法")
    credential_schema: Optional[ServiceCredentialSchema] = Field(
        default=None, description="个人业务凭据需求声明"
    )
    trusted_credential_recipient: bool = Field(
        default=False, description="是否为经管理员审核的可信凭据接收方"
    )


class ServiceMetadataUpdate(BaseModel):
    """服务元数据修改请求"""

    name: Optional[str] = Field(default=None, description="服务显示名称")
    description: Optional[str] = Field(default=None, description="业务描述")
    owner: Optional[str] = Field(default=None, description="维护人员/团队")
    category: Optional[str] = Field(default=None, description="业务分类标签")
    auth_mode: Optional[str] = Field(default=None, description="认证模式")
    auth_label: Optional[str] = Field(default=None, description="认证方式显示标签")
    auth_guide: Optional[str] = Field(default=None, description="统一认证引导说明")
    auth_entry_url: Optional[str] = Field(default=None, description="统一认证跳转入口地址")
    usage_examples: Optional[List[str]] = Field(default=None, description="适用场景与示例问法")


class CredentialTrustUpdate(BaseModel):
    """管理员独立确认凭据接收方是否可信请求"""

    trusted: bool = Field(..., description="是否确认为可信凭据接收方")


class ToolPolicyUpdate(BaseModel):
    """工具治理策略修改请求"""

    risk_level: ToolRiskLevel = Field(..., description="风险等级")
    requires_confirmation: bool = Field(default=False, description="是否需要人工确认")


class InvocationLogItem(BaseModel):
    """工具调用审计日志模型"""

    id: str = Field(..., description="日志唯一标识")
    timestamp: str = Field(..., description="调用时间戳 ISO 格式")
    user_id: str = Field(default="default-agent", description="调用主体")
    client_id: str = Field(default="mcp-client", description="客户端应用")
    service_id: str = Field(..., description="服务标识")
    tool_name: str = Field(..., description="工具名称")
    params_summary: Dict[str, Any] = Field(default_factory=dict, description="脱敏入参")
    result_status: str = Field(..., description="执行结果状态")
    duration_ms: float = Field(..., description="调用耗时（毫秒）")
    trace_id: Optional[str] = Field(default="", description="链路追踪 ID")


# --- 面向非开发者的公开门户 (Capability Portal) 数据模型 ---


class PortalTrendItem(BaseModel):
    """每日调用趋势数据点"""

    date: str = Field(..., description="日期 YYYY-MM-DD")
    calls: int = Field(default=0, description="调用次数")
    success_calls: int = Field(default=0, description="成功调用次数")


class PortalOverview(BaseModel):
    """公开门户运行概览（真实数据驱动）"""

    services_count: int = Field(default=0, description="已发布可用能力数")
    tools_count: int = Field(default=0, description="可用工具总数")
    total_calls: int = Field(default=0, description="累计真实总调用量")
    active_services_count: int = Field(default=0, description="在线可用服务数")
    health_rate: float = Field(default=100.0, description="整体服务健康率(%)")
    daily_trends: List[PortalTrendItem] = Field(
        default_factory=list, description="近7日调用趋势"
    )


class PortalCapabilityCard(BaseModel):
    """门户公开能力卡片（严格脱敏，不含真实内网地址与内部联系人）"""

    id: str = Field(..., description="服务唯一标识")
    name: str = Field(..., description="服务友好展示名称")
    description: str = Field(default="", description="业务说明简介")
    category: str = Field(default="通用", description="分类标签")
    tools_count: int = Field(default=0, description="可用工具数")
    status: ServiceStatus = Field(default=ServiceStatus.ACTIVE, description="健康状态")
    auth_mode: str = Field(default="platform_sso", description="认证模式")
    auth_label: str = Field(default="Hub 统一认证", description="认证方式标签")
    auth_guide: str = Field(default="", description="统一认证引导说明")
    auth_entry_url: str = Field(default="", description="统一认证入口")
    call_count: int = Field(default=0, description="累计真实调用次数")
    recent_calls_7d: int = Field(default=0, description="近7日调用次数")
    last_active_at: Optional[str] = Field(default=None, description="最后活跃时间")
    created_at: datetime = Field(..., description="上线时间")


class PortalToolItem(BaseModel):
    """门户展示的工具项（突出通俗可读，技术 Schema 可折叠）"""

    id: str = Field(default="", description="工具唯一 ID")
    name: str = Field(..., description="工具原始名称")
    namespace_name: str = Field(..., description="统一网关工具命名空间名称")
    description: str = Field(default="", description="业务功能通俗说明")
    risk_level: ToolRiskLevel = Field(default=ToolRiskLevel.L0, description="风险等级")
    requires_confirmation: bool = Field(default=False, description="是否需确认")
    requires_credentials: bool = Field(default=False, description="是否需要个人业务凭据")
    input_schema: Dict[str, Any] = Field(
        default_factory=dict, description="技术参数 Schema"
    )


class PortalCapabilityDetail(BaseModel):
    """门户单个能力完整公开详情（严格脱敏）"""

    id: str = Field(..., description="服务唯一标识")
    name: str = Field(..., description="展示名称")
    description: str = Field(default="", description="业务说明")
    category: str = Field(default="通用", description="分类标签")
    version: str = Field(default="1.0.0", description="版本号")
    status: ServiceStatus = Field(default=ServiceStatus.ACTIVE, description="服务状态")
    created_at: datetime = Field(..., description="上线时间")
    auth_mode: str = Field(default="platform_sso", description="认证模式")
    auth_label: str = Field(default="Hub 统一认证", description="认证方式标签")
    auth_guide: str = Field(default="", description="统一认证引导说明")
    auth_entry_url: str = Field(default="", description="统一认证跳转入口")
    credential_schema: Optional[ServiceCredentialSchema] = Field(
        default=None, description="个人业务凭据需求声明"
    )
    usage_examples: List[str] = Field(
        default_factory=list, description="适用场景与示例问法"
    )
    gateway_url: str = Field(..., description="Hub 统一对外 MCP Gateway 地址")
    protocol: str = Field(default="Streamable HTTP", description="传输协议")
    tools: List[PortalToolItem] = Field(default_factory=list, description="工具列表")
    total_calls: int = Field(default=0, description="累计真实调用次数")
    recent_calls_7d: int = Field(default=0, description="近7日调用次数")
    daily_trends: List[PortalTrendItem] = Field(
        default_factory=list, description="近7日调用趋势"
    )
    last_active_at: Optional[str] = Field(default=None, description="最后活跃时间")

