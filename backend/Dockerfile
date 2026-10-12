# Backend image for the optional Docker stack (`make up`).
# Production-style: locked deps, no dev extras, no --reload. For development,
# run `make backend` natively instead.

FROM python:3.13-slim-bookworm AS build

COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first so source edits don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable


FROM python:3.13-slim-bookworm

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY --from=build --chown=app:app /app/.venv /app/.venv

# Compose bind-mounts backend/.env, exports/ and the genre catalog here and runs
# as the host user, which may have no passwd entry, so HOME must be writable.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

USER app
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/capabilities', timeout=4)"]

CMD ["uvicorn", "explorator.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
