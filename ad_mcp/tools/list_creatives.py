import json
import logging
from adcp.client import ADCPClient
from adcp.testing import CREATIVE_AGENT_CONFIG
from adcp.types import ListCreativeFormatsRequest
from ad_mcp.server import AD_MCP

logger = logging.getLogger(__name__)


@AD_MCP.tool()
async def list_creatives(
    name_search: str = "",
    asset_types: list = None,
    min_width: int = None,
    max_width: int = None,
    min_height: int = None,
    max_height: int = None,
    is_responsive: bool = None,
) -> str:
    """
    Discover available ad creative formats from the creative agent.
    All parameters are optional filters.

    Args:
        name_search:   Case-insensitive partial match on format name (e.g. 'generative', 'video').
        asset_types:   Filter to formats using these asset types.
                       Valid values: 'image', 'video', 'audio', 'text', 'html', 'javascript', 'url'.
        min_width:     Minimum format width in pixels (inclusive).
        max_width:     Maximum format width in pixels (inclusive).
        min_height:    Minimum format height in pixels (inclusive).
        max_height:    Maximum format height in pixels (inclusive).
        is_responsive: If true, return only responsive formats with no fixed dimensions.
    """
    logger.info(
        "[list_creatives] Tool called — name_search=%r asset_types=%r "
        "width=%s-%s height=%s-%s is_responsive=%s",
        name_search, asset_types,
        min_width or "any", max_width or "any",
        min_height or "any", max_height or "any",
        is_responsive,
    )

    kwargs: dict = {}
    if name_search:
        kwargs["name_search"] = name_search
    if asset_types:
        kwargs["asset_types"] = asset_types
    if min_width is not None:
        kwargs["min_width"] = min_width
    if max_width is not None:
        kwargs["max_width"] = max_width
    if min_height is not None:
        kwargs["min_height"] = min_height
    if max_height is not None:
        kwargs["max_height"] = max_height
    if is_responsive is not None:
        kwargs["is_responsive"] = is_responsive

    try:
        logger.info("[list_creatives] Connecting to creative agent at %s",
                    CREATIVE_AGENT_CONFIG.agent_uri)
        async with ADCPClient(CREATIVE_AGENT_CONFIG) as client:
            result = await client.list_creative_formats(ListCreativeFormatsRequest(**kwargs))

        if not result.success:
            logger.error("[list_creatives] API returned failure: %s", result.error)
            return json.dumps({"result": "failed", "error": result.error})

        formats = []
        for fmt in result.data.formats:
            fid = fmt.format_id
            formats.append({
                "format_id": fid.id,
                "width": fid.width,
                "height": fid.height,
                "assets": [
                    {"asset_id": a.asset_id, "type": a.asset_type, "required": a.required}
                    for a in fmt.assets
                ],
            })

        logger.info("[list_creatives] Success — returned %d formats", len(formats))
        return json.dumps({"result": "success", "formats": formats})

    except Exception as exc:
        logger.exception("[list_creatives] Unexpected error: %s", exc)
        return json.dumps({"result": "failed", "error": str(exc)})
