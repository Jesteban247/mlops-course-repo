FROM python:3.14-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-cache

COPY api.py inference.py model_utils.py train.py ./
COPY models ./models

EXPOSE 8989

CMD ["uv", "run", "--no-dev", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8989"]
