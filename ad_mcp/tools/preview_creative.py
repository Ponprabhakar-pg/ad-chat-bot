import os
import json
from adcp.testing import test_agent
from adcp.types import PreviewCreativeRequest
from ad_mcp.server import AD_MCP


@AD_MCP.tool()
async def preview_creative(format_id: str) -> str:
    """
    preview_creative generates visual previews of ad creative manifests in AdCP in single or batch mode returning URL, image, or HTML output.
    """
    try:
        result = await test_agent.preview_creative(
            PreviewCreativeRequest(manifest={"format_id": format_id})
        )

        if hasattr(result, 'errors') and result.errors:
            raise Exception(f"Failed: {result.errors}")
        return json.dumps({"result": "success", "data": result})
    except Exception as e:
        return json.dumps({"result": "failed", "error": str(e)})
