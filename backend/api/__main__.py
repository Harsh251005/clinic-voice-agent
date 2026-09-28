"""uv run python -m api: serve the call links on API_HOST:API_PORT."""

import logging
import sys

import uvicorn

from clinic_agent.config import ConfigError, load_settings
from clinic_agent.store.migrations import SchemaOutdated

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

try:
    from api.app import create_app

    cfg = load_settings()
    app = create_app(cfg)
except (ConfigError, SchemaOutdated) as err:
    sys.exit(f"configuration error: {err}")

print(f"call links: {cfg.public_base_url}/call/<link name>  (listening on {cfg.api_host}:{cfg.api_port})", flush=True)
uvicorn.run(app, host=cfg.api_host, port=cfg.api_port, server_header=False, log_level="warning")
