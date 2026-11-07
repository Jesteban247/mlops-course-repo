#!/bin/sh
set -e

echo "Running unit tests before starting the API..."
python -m pytest -v --cov=app --cov-report=term-missing
echo "All unit tests passed. Starting FastAPI..."
exec uvicorn app:app --host 0.0.0.0 --port 8000
