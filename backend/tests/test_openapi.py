"""The frontend's copy of the API schema must match the API."""

import json
from pathlib import Path

from api.openapi import schema

COMMITTED = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "api" / "openapi.json"


def test_frontend_api_schema_is_current(env):
    assert COMMITTED.exists(), "run `npm run api:types` in frontend/"
    assert json.loads(COMMITTED.read_text()) == schema(), (
        "The dashboard API changed: run `npm run api:types` in frontend/ and commit the result."
    )
