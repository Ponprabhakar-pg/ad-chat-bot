import os
import json
from adcp.testing import test_agent
from adcp.types import ListCreativeFormatsRequest
from ad_mcp.server import AD_MCP


@AD_MCP.tool()
async def list_creatives() -> str:
    """
    list_creative_formats discovers available ad format specifications from any AdCP agent, including asset requirements and technical constraints.
    Discover creative formats supported by a creative agent. Returns full format specifications including asset requirements and technical constraints.
    """
    try:
        result = await test_agent.list_creative_formats(
            ListCreativeFormatsRequest()
        )

        if hasattr(result, 'errors') and result.errors:
            raise Exception(f"Failed: {result.errors}")
        return json.dumps({"result": "success", "data": result})
    except Exception as e:
        return json.dumps({"result": "failed", "error": str(e)})
