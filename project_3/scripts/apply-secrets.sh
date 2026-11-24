#!/usr/bin/env bash
set -euo pipefail

PROJECT3_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(git -C "$PROJECT3_DIR" rev-parse --show-toplevel)"
cd "$REPO_DIR"

if [ ! -s project_3/.env ]; then
  echo 'Missing project_3/.env' >&2
  exit 1
fi

python3 - <<'PYTHON'
from pathlib import Path
import secrets
path = Path('project_3/.env')
content = path.read_text()
keys = {line.split('=', 1)[0] for line in content.splitlines() if '=' in line}
additions = []
if 'GRAFANA_USERNAME' not in keys:
    additions.append('GRAFANA_USERNAME=admin')
if 'GRAFANA_PASSWORD' not in keys:
    additions.append('GRAFANA_PASSWORD=' + secrets.token_urlsafe(24))
if additions:
    with path.open('a') as env:
        env.write('\n' + '\n'.join(additions) + '\n')
PYTHON

set -a
. project_3/.env
set +a
: "${AIRFLOW_FERNET_KEY:?Missing AIRFLOW_FERNET_KEY}"
: "${AIRFLOW_API_SECRET:?Missing AIRFLOW_API_SECRET}"
: "${AIRFLOW_JWT_SECRET:?Missing AIRFLOW_JWT_SECRET}"
: "${AIRFLOW_DB_USER:?Missing AIRFLOW_DB_USER}"
: "${AIRFLOW_DB_PASSWORD:?Missing AIRFLOW_DB_PASSWORD}"
: "${AIRFLOW_DB_NAME:?Missing AIRFLOW_DB_NAME}"

umask 077
PROJECT3_ENV_FILE="$(mktemp)"
trap 'rm -f "$PROJECT3_ENV_FILE"' EXIT
awk -F= '$1 != "CODE_VERSION" && $1 !~ /^ARGOCD_/ {print}' project_3/.env > "$PROJECT3_ENV_FILE"
PROJECT3_CODE_VERSION="$(git rev-parse HEAD)"
if [ -n "$(git status --porcelain -- project_3/src project_3/dags project_3/sql)" ]; then
  PROJECT3_CODE_VERSION="${PROJECT3_CODE_VERSION}-dirty"
fi
printf '\nCODE_VERSION=%s\n' "$PROJECT3_CODE_VERSION" >> "$PROJECT3_ENV_FILE"

kubectl create namespace project-3 --dry-run=client -o yaml | kubectl apply -f -
kubectl -n project-3 create secret generic project-3-settings --from-env-file="$PROJECT3_ENV_FILE" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n project-3 create secret generic project-3-airflow-fernet --from-literal=fernet-key="$AIRFLOW_FERNET_KEY" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n project-3 create secret generic project-3-airflow-api --from-literal=api-secret-key="$AIRFLOW_API_SECRET" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n project-3 create secret generic project-3-airflow-jwt --from-literal=jwt-secret="$AIRFLOW_JWT_SECRET" --dry-run=client -o yaml | kubectl apply -f -
kubectl -n project-3 create secret generic project-3-airflow-metadata \
  --from-literal=connection="postgresql+psycopg2://${AIRFLOW_DB_USER}:${AIRFLOW_DB_PASSWORD}@airflow-postgres:5432/${AIRFLOW_DB_NAME}" \
  --dry-run=client -o yaml | kubectl apply -f -
