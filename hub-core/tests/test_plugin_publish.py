"""测试 MCP 插件自助上传、预检与发布 API"""

import io
import json
import zipfile
import pytest
from fastapi.testclient import TestClient

from src.main import build_app


@pytest.fixture
def client(monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "admin_api_key", "test-admin-secret-key")
    app = build_app()
    with TestClient(app, headers={"X-Admin-Key": "test-admin-secret-key"}) as c:
        yield c


def _create_mock_zip(manifest: dict, server_code: str = "print('hello')", extra_files: dict = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("server.py", server_code)
        if extra_files:
            for fname, content in extra_files.items():
                zf.writestr(fname, content)
    buf.seek(0)
    return buf.getvalue()


def test_download_template_zip(client: TestClient):
    """测试下载脚手架模板包"""
    resp = client.get("/api/v1/plugins/template/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "python-mcp-demo.zip" in resp.headers["content-disposition"]

    # 验证 zip 可读且包含核心文件
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert "server.py" in names
        assert "agent.md" in names


def test_inspect_valid_plugin_zip(client: TestClient):
    """测试合法插件包预检"""
    manifest = {
        "manifest_version": "1.0.0",
        "service_id": "test-mock-service",
        "name": "测试 Mock 服务",
        "version": "1.0.0",
        "description": "这是一个测试插件",
        "author": "tester",
        "port": 8000,
        "tools": [
            {"name": "query_test", "description": "测试查询", "risk_level": "L0"}
        ]
    }
    server_py = "from fastmcp import FastMCP\nmcp = FastMCP('test')\n"
    zip_bytes = _create_mock_zip(manifest, server_py)

    resp = client.post(
        "/api/v1/plugins/inspect",
        files={"file": ("test-plugin.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["service_id"] == "test-mock-service"
    assert data["name"] == "测试 Mock 服务"
    assert len(data["tools"]) == 1


def test_inspect_invalid_plugin_zip_missing_server(client: TestClient):
    """测试缺少 server.py 的非法包"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"service_id": "bad-plugin"}))
    buf.seek(0)

    resp = client.post(
        "/api/v1/plugins/inspect",
        files={"file": ("bad.zip", buf.getvalue(), "application/zip")},
    )
    assert resp.status_code == 400
    assert "缺少核心入口文件" in resp.json()["detail"]


def test_inspect_invalid_service_id(client: TestClient):
    """测试 service_id 不合规"""
    manifest = {
        "service_id": "123_INVALID",
        "name": "非法ID",
    }
    zip_bytes = _create_mock_zip(manifest)
    resp = client.post(
        "/api/v1/plugins/inspect",
        files={"file": ("bad_id.zip", zip_bytes, "application/zip")},
    )
    assert resp.status_code == 400
    assert "不合规" in resp.json()["detail"]
