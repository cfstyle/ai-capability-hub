"""Hub Core 配置加载模块

支持从环境变量和 YAML 文件加载配置。环境变量优先级高于 YAML。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class UpstreamService(BaseModel):
    """上游 MCP 服务描述"""

    service_id: str = Field(description="服务唯一标识，用作工具命名空间前缀")
    endpoint_url: str = Field(description="MCP Streamable HTTP 地址")
    enabled: bool = Field(default=True)


class HubConfig(BaseSettings):
    """Hub Core 配置

    字段按优先级从高到低加载：环境变量 > YAML 文件 > 默认值
    环境变量前缀：HUB_（例如 HUB_PORT=9090）
    """

    hub_name: str = Field(default="AI Capability Hub", description="Hub 实例名称")
    hub_version: str = Field(default="0.2.2", description="Hub 版本号")
    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8080, description="监听端口")
    database_url: str = Field(
        default="sqlite:///data/hub.db",
        description="数据库连接串",
    )
    log_level: str = Field(default="INFO", description="日志级别")
    mcp_endpoint_path: str = Field(
        default="/mcp",
        description="MCP Streamable HTTP 端点路径",
    )
    admin_api_key: Optional[str] = Field(
        default=None,
        description="管理 API 密钥（MVP 用于简单认证）",
    )
    public_mcp_url: Optional[str] = Field(
        default=None,
        description="对外暴露的统一 Gateway 入口 URL（例如 http://hub.example.com/mcp）",
    )
    upstream_services: List[UpstreamService] = Field(
        default_factory=lambda: [
            UpstreamService(
                service_id="ticm",
                endpoint_url=os.getenv("TICM_ENDPOINT_URL", "http://localhost:8081/mcp"),
            )
        ],
        description="启动时自动挂载的上游 MCP 服务列表",
    )

    model_config = {
        "env_prefix": "HUB_",
        "env_file": ".env",
        "extra": "ignore",
    }


def _load_yaml_overrides(yaml_path: str = "config.yaml") -> dict:
    """从 YAML 文件加载配置覆盖值"""
    path = Path(yaml_path)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def load_config(yaml_path: str = "config.yaml") -> HubConfig:
    """加载 Hub 配置

    加载顺序：默认值 -> YAML 文件 -> 环境变量（后者覆盖前者）

    Args:
        yaml_path: YAML 配置文件路径

    Returns:
        HubConfig 实例
    """
    yaml_overrides = _load_yaml_overrides(yaml_path)
    return HubConfig(**yaml_overrides)


settings = load_config()


