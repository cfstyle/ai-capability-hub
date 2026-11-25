import os
from fastmcp import FastMCP
from starlette.responses import JSONResponse
mcp = FastMCP('zip-trust')
@mcp.tool()
async def ping() -> dict:
    return {'ok': True}
@mcp.custom_route('/healthz', methods=['GET'])
async def hz(req):
    return JSONResponse({'status': 'ok'})
if __name__ == '__main__':
    mcp.run(transport='streamable-http', host=os.getenv('MCP_HOST','127.0.0.1'), port=int(os.getenv('MCP_PORT','8000')))
