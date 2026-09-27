# Project 1

Run commands from the `project_1` directory.

## Setup

```bash
mkdir -p dags logs plugins config data models
if [ ! -f .env ]; then
  cp .env.example .env
  echo "AIRFLOW_UID=$(id -u)" >> .env
  echo "FERNET_KEY=$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')" >> .env
  echo "JUPYTER_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')" >> .env
  echo "AIRFLOW__API_AUTH__JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" >> .env
  echo "MINIO_ROOT_USER=project1minio" >> .env
  echo "MINIO_ROOT_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')" >> .env
  echo "MINIO_BUCKET=covertype-models" >> .env
  echo "PROJECT_DATA_DB_HOST=project-data-storage" >> .env
  echo "PROJECT_DATA_DB_PORT=5432" >> .env
  echo "PROJECT_DATA_DB_NAME=cover_data" >> .env
  echo "PROJECT_DATA_DB_USER=cover_user" >> .env
  echo "PROJECT_DATA_DB_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')" >> .env
fi
```

## Docker Compose

```bash
docker compose build
docker compose up airflow-init
docker compose up -d
docker compose ps
```

```text
Airflow:    http://localhost:8080
JupyterLab: http://localhost:8888/lab?token=<token-from-jupyter-logs>
MinIO:      http://localhost:9001
Model API:  http://localhost:8000/docs
```

```bash
docker compose logs --tail=50 jupyter
```

Open the Jupyter URL shown in the logs through your SSH tunnel, using `localhost` as the host.

## Airflow DAGs

```text
db_create_cover_samples_table
db_clear_cover_samples_table
db_inspect_cover_samples_table
api_connection_check
api_reset_group_4
extract_cover_data
```

### Data collection note

The API currently uses the requested group number to select the data slice, so group 4 receives samples from the same slice across its batch numbers. The extraction DAG removes duplicate rows within each batch; the same feature row can appear in different batches.

## UV local tests

```bash
uv sync --group tests
uv run tests/api.py
uv run tests/api2.py
uv run tests/api3.py
uv run tests/api4.py
uv run tests/api5.py
```

## SMS test

```bash
uv run tests/test_sms.py
```

## Notebooks

```text
notebooks/01_prepare.ipynb
notebooks/02_train.ipynb
notebooks/03_inference.ipynb
```

## Prediction API

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"features":{"elevation":2596,"aspect":51,"slope":3,"horizontal_distance_to_hydrology":258,"vertical_distance_to_hydrology":0,"horizontal_distance_to_roadways":510,"hillshade_9am":221,"hillshade_noon":232,"hillshade_3pm":148,"horizontal_distance_to_fire_points":6279,"wilderness_area":"1","soil_type":"29"}}'
```

## Stop and remove

```bash
docker compose down
docker compose down --rmi all --volumes --remove-orphans
docker ps -a
docker volume ls
docker image ls
```

## Demo

![API demo](files/Demo.gif)