"""HubAggregator 单元与集成测试"""

import pytest
from fastapi.testclient import TestClient
from fastmcp import FastMCP

from src.gateway.aggregator import HubAggregator, create_aggregator
from src.main import app


def test_aggregator_creation():
    """验证 HubAggregator 初始化参数与属性"""
    aggregator = create_aggregator("Test Hub", "1.0.0")
    assert isinstance(aggregator, HubAggregator)
    assert aggregator.mcp.name == "Test Hub"
    assert aggregator._mounted_services == {}


def test_aggregator_mount_subservice():
    """验证 HubAggregator 记录挂载服务"""
    aggregator = create_aggregator("Test Hub")
    aggregator.mount_service("ticm", "http://localhost:8081/mcp")
    assert "ticm" in aggregator._mounted_services
    assert aggregator._mounted_services["ticm"] == "http://localhost:8081/mcp"


def test_mcp_endpoint_mounted():
    """验证 FastAPI 实例正确挂载了 /mcp 端点并响应"""
    with TestClient(app) as client:
        # initialize 请求
        response = client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-suite", "version": "1.0"},
                },
            },
        )
        assert response.status_code == 200
        assert "AI Capability Hub" in response.text
