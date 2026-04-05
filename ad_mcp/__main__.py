from core.log_config import setup_logging
setup_logging()

from ad_mcp.tools import *  # noqa: F401, F403 — registers @AD_MCP.tool() decorators
from ad_mcp.server import AD_MCP

AD_MCP.run()
