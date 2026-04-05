import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    fmt = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(handler)
    root.setLevel(level)

    for noisy in ("httpx", "httpcore", "hpack", "uvicorn.access", "anyio", "mcp.client.stdio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
