# One image for the backend, run three ways by command (docker-compose.yml):
#   python -m api                             call pages + dashboard API
#   python main.py start                      the voice agent worker
#   python -m clinic_agent.store.migrations   bring the schema up to date
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"

# Dependencies first: this layer is reused until uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

COPY . .
RUN useradd --system --uid 10001 --create-home app && chown -R app /app
USER app

# Secrets come from the environment at run time, never from the image
# (.dockerignore keeps .env out).
ENV API_HOST=0.0.0.0
EXPOSE 8080
CMD ["python", "-m", "api"]
