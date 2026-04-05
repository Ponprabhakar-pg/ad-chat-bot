import sys
import json
import time
import asyncio
import logging
import nest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

nest_asyncio.apply()

logger = logging.getLogger(__name__)

_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "ad_mcp"],
)


async def _list_tools_async() -> list:
    logger.info("[mcp_client] Fetching tool list from MCP server")
    t0 = time.monotonic()
    try:
        async with stdio_client(_SERVER_PARAMS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
        elapsed = time.monotonic() - t0
        logger.info("[mcp_client] Fetched %d tools in %.2fs", len(tools), elapsed)
        return tools
    except Exception as e:
        logger.exception("[mcp_client] Failed to fetch tool list: %s", e)
        raise


async def _call_tool_async(name: str, arguments: dict):
    logger.info("[mcp_client] → call_tool name=%s args=%s", name, arguments)
    t0 = time.monotonic()
    try:
        async with stdio_client(_SERVER_PARAMS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
        elapsed = time.monotonic() - t0
        if result.isError:
            logger.error("[mcp_client] ✗ call_tool name=%s FAILED in %.2fs | content=%s",
                         name, elapsed, result.content)
        else:
            logger.info("[mcp_client] ✓ call_tool name=%s OK in %.2fs", name, elapsed)
        return result
    except Exception as e:
        logger.exception("[mcp_client] ✗ call_tool name=%s raised after %.2fs: %s",
                         name, time.monotonic() - t0, e)
        raise


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def list_tools() -> list:
    return _run(_list_tools_async())


def call_tool(name: str, arguments: dict) -> str:
    try:
        result = _run(_call_tool_async(name, arguments))
        if result.isError:
            return json.dumps({"result": "failed", "error": str(result.content)})
        texts = [c.text for c in result.content if hasattr(c, "text")]
        payload = "\n".join(texts) if texts else str(result.content)
        logger.debug("[mcp_client] call_tool name=%s payload_len=%d", name, len(payload))
        return payload
    except Exception as e:
        logger.error("[mcp_client] call_tool(%s) unhandled error: %s", name, e)
        return json.dumps({"result": "failed", "error": str(e)})


def to_groq_tool(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }
