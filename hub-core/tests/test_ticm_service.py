import asyncio
import json
import runpy
from pathlib import Path

from fastmcp import Client


def test_ticm_bond_detail_known_and_unknown_codes():
    server_path = Path(__file__).resolve().parents[2] / "services" / "ticm-mcp" / "server.py"
    server = runpy.run_path(str(server_path))["mcp"]

    async def check_tool():
        async with Client(server) as client:
            known = await client.call_tool("ticm__bond_detail", {"bond_code": "019547"})
            bond = json.loads(known.content[0].text)
            assert bond["bond_code"] == "019547"
            assert bond["data_status"] == "MOCK"

            unknown = await client.call_tool("ticm__bond_detail", {"bond_code": "111"})
            missing = json.loads(unknown.content[0].text)
            assert missing["bond_code"] == "111"
            assert missing["error"] == "未找到该债券"
            assert "019547" in missing["available_codes"]

    asyncio.run(check_tool())
