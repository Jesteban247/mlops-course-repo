FROM ghcr.io/astral-sh/uv:0.12.10 AS uv
FROM python:3.11.14-slim-bookworm
COPY --from=uv /uv /uvx /usr/local/bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
ARG DEPENDENCY_GROUP=server
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --group ${DEPENDENCY_GROUP}
