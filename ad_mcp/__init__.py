import logging
import uuid
import json
import requests
from ad_mcp.tools import *
from ad_mcp.server import AD_MCP
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()


if __name__ == '__main__':
    AD_MCP.run()