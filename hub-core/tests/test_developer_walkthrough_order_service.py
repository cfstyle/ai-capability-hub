"""完整开发者演练测试：从模板 ZIP 下载、解压、改造为订单服务、打包、走正式发布、并使用 README 地址和配置从外部 MCP 客户端访问运行中的 Hub /mcp"""

import asyncio
import io
import json
import socket
import threading
import time
import zipfile
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from src.main import build_app
from src.gateway.plugin_manager import plugin_manager


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_uvicorn_server(app, host: str = "127.0.0.1") -> tuple[uvicorn.Server, threading.Thread, int]:
    port = _get_free_port()
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 10.0
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://{host}:{port}/healthz", timeout=0.5, trust_env=False)
            if r.status_code == 200:
                return server, thread, port
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("Hub server failed to start within timeout")


@pytest.mark.anyio
async def test_developer_walkthrough_full_cycle(tmp_path, monkeypatch):
    """
    首次开发者演练验收（全链路真实 HTTP 边界）：
    下载模板 ZIP -> 解压 -> 按 README 改名并新增订单查询工具 -> 本地测试 ->
    重新打包 -> 走正式插件预检和发布入口 ->
    使用 README 给出的地址与配置，从外部 MCP 客户端通过 HTTP 访问运行中的 Hub /mcp 发现并调用已发布订单工具。
    """
    admin_key = "test-admin-secret-walkthrough"
    monkeypatch.setenv("HUB_ADMIN_API_KEY", admin_key)
    monkeypatch.setenv("HUB_ENV", "development")

    from src.config import settings, load_config
    load_config.cache_clear()
    settings.admin_api_key = admin_key
    settings.upstream_services = []
    monkeypatch.setenv("HUB_UPSTREAM_SERVICES", "[]")

    db_path = tmp_path / "walkthrough.db"
    monkeypatch.setenv("HUB_DATABASE_URL", f"sqlite:///{db_path}")

    # 隔离 plugin_manager.services_dir，避免污染仓库 services/ 目录
    isolated_services = tmp_path / "services"
    isolated_services.mkdir(parents=True, exist_ok=True)
    import shutil
    repo_demo = Path(__file__).resolve().parents[2] / "services" / "python-mcp-demo"
    shutil.copytree(repo_demo, isolated_services / "python-mcp-demo")
    monkeypatch.setattr(plugin_manager, "services_dir", isolated_services)

    app = build_app()
    server, thread, hub_port = _start_uvicorn_server(app)
    hub_base_url = f"http://127.0.0.1:{hub_port}"

    try:
        async with httpx.AsyncClient(base_url=hub_base_url, trust_env=False, timeout=20.0) as http_client:
            # 步骤 1: 从管理端下载标准脚手架模板 ZIP
            resp = await http_client.get(
                "/api/v1/plugins/template/download",
                headers={"X-Admin-Key": admin_key},
            )
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "application/zip"
            template_zip_bytes = resp.content
            assert len(template_zip_bytes) > 0

            # 步骤 2: 在干净临时目录下解压
            work_dir = tmp_path / "order-service"
            work_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(template_zip_bytes), "r") as zf:
                zf.extractall(work_dir)

            files = [p.name for p in work_dir.iterdir()]
            assert "manifest.json" in files
            assert "server.py" in files
            assert "README.md" in files
            assert "agent.md" in files

            readme_text = (work_dir / "README.md").read_text(encoding="utf-8")
            assert "/mcp" in readme_text
            assert "order-service_query_order" in readme_text

            # 步骤 3: 按照 README 教程改造为 order-service
            manifest_data = {
                "manifest_version": "1.0.0",
                "service_id": "order-service",
                "name": "电商订单服务 MCP",
                "version": "1.0.0",
                "description": "提供订单查询、履约状态追踪及明细核对能力",
                "author": "first-time-developer",
                "entrypoint": "server.py",
                "protocol": "streamable-http",
                "port": 8000,
                "healthz_path": "/healthz",
                "mcp_path": "/mcp",
                "tools": [
                    {
                        "name": "query_order",
                        "description": "根据订单编号查询订单状态、支付金额与商品明细",
                        "risk_level": "L0",
                    }
                ],
            }
            (work_dir / "manifest.json").write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

            server_code = """from __future__ import annotations
import logging, os
from typing import Any, Dict
from fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP("Order Service")

ORDERS_DB = {
    "ORD-2026-001": {
        "order_id": "ORD-2026-001",
        "buyer": "张三",
        "amount": 1299.00,
        "status": "PAID",
        "items": ["智能降噪耳机"],
        "created_at": "2026-11-24 10:00:00",
    },
    "ORD-2026-002": {
        "order_id": "ORD-2026-002",
        "buyer": "李四",
        "amount": 88.50,
        "status": "SHIPPED",
        "items": ["Type-C 数据线 2米"],
        "created_at": "2026-11-24 11:30:00",
    },
}

@mcp.tool()
async def query_order(order_id: str) -> Dict[str, Any]:
    \"\"\"根据订单号查询订单状态与购买明细。\"\"\"
    clean_id = (order_id or "").strip()
    if not clean_id:
        return {"success": False, "error_code": "INVALID_PARAMS", "message": "订单号不能为空"}

    order = ORDERS_DB.get(clean_id)
    if not order:
        return {
            "success": False,
            "error_code": "ORDER_NOT_FOUND",
            "message": f"未找到订单 '{clean_id}'",
            "available_order_examples": list(ORDERS_DB.keys()),
        }

    return {"success": True, "data": order}

@mcp.custom_route("/healthz", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "healthy", "service": "Order Service", "tools_count": 1})

if __name__ == "__main__":
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="streamable-http", host=host, port=port)
"""
            (work_dir / "server.py").write_text(server_code, encoding="utf-8")

            test_code = """import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import mcp, query_order
from fastmcp import Client

def test_query_existing():
    res = asyncio.run(query_order(order_id="ORD-2026-001"))
    assert res["success"] is True
    assert res["data"]["buyer"] == "张三"
    assert res["data"]["amount"] == 1299.00

def test_query_not_found():
    res = asyncio.run(query_order(order_id="ORD-999-NOT-FOUND"))
    assert res["success"] is False
    assert res["error_code"] == "ORDER_NOT_FOUND"

def test_mcp_client_protocol():
    async def _test():
        async with Client(mcp) as client:
            tools = await client.list_tools()
            assert any(t.name == "query_order" for t in tools)
            call_res = await client.call_tool("query_order", {"order_id": "ORD-2026-002"})
            assert call_res.is_error is False
            assert "李四" in call_res.content[0].text
    asyncio.run(_test())
"""
            tests_dir = work_dir / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            (tests_dir / "test_server.py").write_text(test_code, encoding="utf-8")

            # 运行改造后的本地测试
            import subprocess, sys
            local_pytest = subprocess.run(
                [sys.executable, "-m", "pytest", "-v", str(tests_dir)],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert local_pytest.returncode == 0, f"本地测试失败:\n{local_pytest.stdout}\n{local_pytest.stderr}"

            # 步骤 4: 验证本地服务工具发现与调用
            import importlib.util
            spec = importlib.util.spec_from_file_location("order_server", str(work_dir / "server.py"))
            order_server_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(order_server_mod)

            async with Client(order_server_mod.mcp) as local_client:
                local_tools = await local_client.list_tools()
                assert any(t.name == "query_order" for t in local_tools)
                local_call = await local_client.call_tool("query_order", {"order_id": "ORD-2026-001"})
                assert "张三" in local_call.content[0].text

            # 步骤 5: 重新打包为 ZIP
            order_zip_buf = io.BytesIO()
            with zipfile.ZipFile(order_zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for item in ["manifest.json", "server.py", "requirements.txt", "README.md", "agent.md", "tests/test_server.py"]:
                    fpath = work_dir / item
                    if fpath.exists():
                        zf.write(fpath, arcname=item)
            order_zip_bytes = order_zip_buf.getvalue()

            # 步骤 6: 走正式插件预检入口 POST /api/v1/plugins/inspect
            inspect_resp = await http_client.post(
                "/api/v1/plugins/inspect",
                files={"file": ("order-service.zip", order_zip_bytes, "application/zip")},
                headers={"X-Admin-Key": admin_key},
            )
            assert inspect_resp.status_code == 200, f"预检失败: {inspect_resp.text}"
            inspect_data = inspect_resp.json()
            assert inspect_data["valid"] is True
            assert inspect_data["service_id"] == "order-service"

            # 步骤 7: 走正式发布入口 POST /api/v1/plugins/publish
            publish_resp = await http_client.post(
                "/api/v1/plugins/publish",
                files={"file": ("order-service.zip", order_zip_bytes, "application/zip")},
                headers={"X-Admin-Key": admin_key},
            )
            assert publish_resp.status_code == 200, f"发布失败: {publish_resp.text}"
            published = publish_resp.json()
            assert published["id"] == "order-service"
            assert published["status"] == "active"
            assert "/mcp" in published["endpoint_url"]

            # 步骤 8: 严格按照 README 给出的地址和配置，从外部 MCP 客户端访问运行中的 Hub /mcp
            login_resp = await http_client.post(
                "/api/v1/portal/auth/login",
                json={"user_id": "walkthrough-dev", "user_name": "演练开发者"},
            )
            assert login_resp.status_code == 200
            user_token = login_resp.json()["token"]

            cfg_resp = await http_client.get(
                "/api/v1/portal/my-config",
                headers={"Authorization": f"Bearer {user_token}"},
            )
            assert cfg_resp.status_code == 200
            cfg_data = cfg_resp.json()
            mcp_cfg = cfg_data["config_templates"]["cursor"]["mcpServers"]["ai-capability-hub"]
            assert mcp_cfg["url"] == f"{hub_base_url}/mcp"
            assert cfg_data["user_id"] == "walkthrough-dev"
            assert mcp_cfg["headers"]["Authorization"] == f"Bearer {cfg_data['token']}"

            # 通过真实 HTTP StreamableHttpTransport 连接运行中的 Hub /mcp（不直接调用 aggregator 或 middleware）
            transport = StreamableHttpTransport(mcp_cfg["url"], headers=mcp_cfg["headers"])
            async with Client(transport) as external_client:
                hub_tools = await external_client.list_tools()
                hub_tool_names = [t.name for t in hub_tools]
                assert "order-service_query_order" in hub_tool_names

                # 8.1 真实调用有效订单
                valid_call = await external_client.call_tool("order-service_query_order", {"order_id": "ORD-2026-001"})
                assert valid_call.is_error is False
                assert "张三" in valid_call.content[0].text
                assert "1299" in valid_call.content[0].text

                # 8.2 真实调用无效订单
                invalid_call = await external_client.call_tool("order-service_query_order", {"order_id": "ORD-999-NOT-FOUND"})
                assert "ORDER_NOT_FOUND" in invalid_call.content[0].text
    finally:
        plugin_manager.stop_service("order-service")
        server.should_exit = True
        thread.join(timeout=5)
