"""Print the dashboard API's OpenAPI schema, for the frontend's generated types.

    uv run python -m api.openapi > ../frontend/src/lib/api/openapi.json

Run by `npm run api:types` in frontend/. tests/test_openapi.py fails when the
committed copy is stale, so an API change can't silently break the screens.
"""

import json

from fastapi import FastAPI

from api import dashboard
from clinic_agent.config import load_settings


def schema() -> dict:
    app = FastAPI(title="Clinic Console API", version="1")
    app.include_router(dashboard.router(load_settings()))
    return app.openapi()


if __name__ == "__main__":
    print(json.dumps(schema(), indent=2, sort_keys=True))
