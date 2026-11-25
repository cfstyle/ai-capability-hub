"""基础健康检查测试"""

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_healthz_returns_200():
    """GET /healthz 应返回 200 和 status ok"""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_readyz_returns_200():
    """GET /readyz 应返回 200"""
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
