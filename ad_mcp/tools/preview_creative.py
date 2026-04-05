import json
import logging
import anyio
from pydantic import ValidationError
from adcp.client import ADCPClient
from adcp.testing import CREATIVE_AGENT_CONFIG
from adcp.types import PreviewCreativeSingleRequest
from ad_mcp.server import AD_MCP

logger = logging.getLogger(__name__)

_AGENT_URL = "https://creative.adcontextprotocol.org/"
_TIMEOUT_SECONDS = 30


def _inject_agent_url(manifest: dict) -> dict:
    fmt = manifest.get("format_id")
    if isinstance(fmt, str):
        manifest["format_id"] = {"agent_url": _AGENT_URL, "id": fmt}
    elif isinstance(fmt, dict) and "agent_url" not in fmt:
        fmt["agent_url"] = _AGENT_URL
    return manifest


@AD_MCP.tool()
async def preview_creative(creative_manifest: dict) -> str:
    """
    Generate a visual preview of an ad creative and return embeddable HTML.

    Accepts a creative_manifest matching the AdCP creative manifest schema:
    - format_id: object with 'id' field (format ID from list_creatives)
    - assets: dict keyed by asset_id (from list_creatives format spec) →
              asset objects, e.g.:
              - text/generative: {"content": "your text or prompt"}
              - image/video/audio: {"url": "https://...", "width": N, "height": N}

    Example for a generative display format:
    {
      "format_id": {"id": "display_300x250_generative"},
      "assets": {"generation_prompt": {"content": "A coffee brand ad"}}
    }
    """
    logger.info("[preview_creative] Tool called — manifest keys=%s",
                list(creative_manifest.keys()))

    # Inject agent_url so the SDK knows which creative agent to call
    creative_manifest = _inject_agent_url(creative_manifest)
    logger.debug("[preview_creative] Manifest after agent_url injection: format_id=%s assets=%s",
                 creative_manifest.get("format_id"), list(creative_manifest.get("assets", {}).keys()))

    # Build full request dict — always output html for embedding in the UI
    request_data = {
        "request_type": "single",
        "creative_manifest": creative_manifest,
        "output_format": "html",
    }

    # Dynamic Pydantic validation against the adcp SDK model
    try:
        request = PreviewCreativeSingleRequest.model_validate(request_data)
        logger.info("[preview_creative] Pydantic validation passed")
    except ValidationError as exc:
        errors = exc.errors()
        logger.warning("[preview_creative] Pydantic validation failed: %s", errors)
        return json.dumps({
            "result": "invalid_request",
            "error": f"Creative manifest validation failed: {errors[0]['msg'] if errors else str(exc)}",
        })

    try:
        logger.info("[preview_creative] Requesting preview (timeout=%ds)", _TIMEOUT_SECONDS)
        with anyio.fail_after(_TIMEOUT_SECONDS):
            async with ADCPClient(CREATIVE_AGENT_CONFIG) as client:
                result = await client.preview_creative(request)

        if not result.success:
            error_msg = result.error or "Creative agent returned an unsuccessful response"
            logger.error("[preview_creative] API failure: %s", error_msg)
            return json.dumps({"result": "failed", "error": error_msg})

        previews = getattr(result.data, "previews", [])
        renders = getattr(previews[0], "renders", []) if previews else []
        if not renders:
            logger.error("[preview_creative] No renders returned")
            return json.dumps({"result": "failed", "error": "No renders returned"})

        render = renders[0]
        dim = getattr(render, "dimensions", None)
        width = int(dim.width) if dim and dim.width else 300
        height = int(dim.height) if dim and dim.height else 250
        format_id = creative_manifest.get("format_id", {}).get("id", "")

        logger.info("[preview_creative] Success — format=%s dimensions=%dx%d html_len=%d",
                    format_id, width, height, len(getattr(render, "preview_html", "") or ""))
        return json.dumps({
            "result": "success",
            "preview_html": getattr(render, "preview_html", ""),
            "width": width,
            "height": height,
            "format_id": format_id,
        })

    except TimeoutError:
        logger.error("[preview_creative] Timed out after %ds", _TIMEOUT_SECONDS)
        return json.dumps({"result": "failed", "error": f"Preview timed out after {_TIMEOUT_SECONDS}s"})
    except Exception as exc:
        exc_str = str(exc)
        # ConnectError / network failures from the creative agent
        if "ConnectError" in type(exc).__name__ or "ConnectError" in exc_str:
            logger.error("[preview_creative] Network error reaching creative agent: %s", exc_str)
            return json.dumps({"result": "failed", "error": "Could not connect to the creative agent. Please try again."})
        logger.exception("[preview_creative] Unexpected error: %s", exc)
        return json.dumps({"result": "failed", "error": str(exc)})
