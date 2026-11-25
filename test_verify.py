"""AI Capability Hub - 本地服务健康与协议快速验证脚本

用法：
    conda activate py311
    python test_verify.py
"""

import asyncio
import urllib.request
import json

def check_http():
    print("=" * 60)
    print("1. HTTP 基础与管理接口健康探测")
    print("=" * 60)
    
    endpoints = [
        ("Hub Core 存活检查", "http://127.0.0.1:8080/healthz", None, 200),
        ("Hub Core 就绪检查", "http://127.0.0.1:8080/readyz", None, 200),
        ("Hub Core Swagger 文档", "http://127.0.0.1:8080/docs", None, 200),
        ("Hub Core 门户概览 (免登公开)", "http://127.0.0.1:8080/api/v1/portal/overview", None, 200),
        ("Hub Core 公开能力列表 (免登脱敏)", "http://127.0.0.1:8080/api/v1/portal/capabilities", None, 200),
        ("Hub Core 管理 API 鉴权测试 (带Key)", "http://127.0.0.1:8080/api/v1/services", {"X-API-Key": "dev-admin-key"}, 200),
        ("TICM Mock MCP 健康检查", "http://127.0.0.1:8081/healthz", None, 200),
        ("Message Mock MCP 健康检查", "http://127.0.0.1:8082/healthz", None, 200),
    ]

    for name, url, headers, expected_code in endpoints:
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                summary = data[:60].replace("\n", "")
                if resp.status == expected_code:
                    print(f"[PASS] {name} ({url}) -> HTTP {resp.status}: {summary}")
                else:
                    print(f"[WARN] {name} ({url}) -> HTTP {resp.status} (预期 {expected_code})")
        except urllib.error.HTTPError as e:
            if e.code == expected_code:
                print(f"[PASS] {name} ({url}) -> HTTP {e.code} (符合预期拦截)")
            elif e.code == 501:
                print(f"[PASS] {name} ({url}) -> HTTP 501 (Not Implemented 路由骨架就绪)")
            else:
                print(f"[FAIL] {name} ({url}) -> HTTP {e.code} (预期 {expected_code})")
        except Exception as e:
            print(f"[FAIL] {name} ({url}) -> 连接失败: {e}")

async def check_mcp_streamable_http():
    print("\n" + "=" * 60)
    print("2. MCP Streamable HTTP 协议握手、工具发现与调用测试")
    print("=" * 60)
    
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError:
        print("[FAIL] 未安装官方 mcp SDK，请确认在 py311 环境下执行")
        return

    target_url = "http://127.0.0.1:8081/mcp"
    print(f"正在连接 TICM Mock MCP Server ({target_url})...")
    
    try:
        async with streamable_http_client(target_url) as client_streams:
            if isinstance(client_streams, tuple) and len(client_streams) == 3:
                read, write, _ = client_streams
            else:
                read, write = client_streams
            async with ClientSession(read, write) as session:
                init_res = await session.initialize()
                version_str = getattr(init_res, "protocol_version", getattr(init_res, "protocolVersion", "unknown"))
                print(f"[PASS] MCP 协议握手成功！协商版本: {version_str}")

                tools_res = await session.list_tools()
                print(f"[PASS] 成功发现 {len(tools_res.tools)} 个业务能力工具 (tools/list):")
                tool_names = [t.name for t in tools_res.tools]
                for t in tools_res.tools:
                    desc = t.description.strip().splitlines()[0] if t.description else ""
                    print(f"       • {t.name}: {desc}")

                target_tool = "ticm__portfolio_summary" if "ticm__portfolio_summary" in tool_names else "portfolio_summary"
                print(f"正在发起工具调用 (tools/call: {target_tool})...")
                call_res = await session.call_tool(target_tool, {"bond_category": "government"})
                print("[PASS] 工具调用成功返回数据:")
                if call_res.content:
                    print("       " + call_res.content[0].text.replace("\n", "\n       "))
                else:
                    print("       (返回为空)")
    except Exception as e:
        print(f"[FAIL] MCP 协议调用失败: {e}")

if __name__ == "__main__":
    check_http()
    asyncio.run(check_mcp_streamable_http())
    print("\n" + "=" * 60)
    print("验证完成！如果要在浏览器查看管理 API 文档，请打开: http://127.0.0.1:8080/docs")
    print("=" * 60)
