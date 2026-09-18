# Assignment 3

Run commands from `assignment3`.

## Setup

```bash
curl -LfO 'https://airflow.apache.org/docs/apache-airflow/3.3.2/docker-compose.yaml'

mkdir -p dags logs plugins config data models
echo "AIRFLOW_UID=$(id -u)" > .env
echo "FERNET_KEY=$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')" >> .env
```

Download the CSV into the shared `data` folder:

```bash
curl -L --retry 3 -o data/penguins.csv \
  https://cdn.jsdelivr.net/gh/mwaskom/seaborn-data@master/penguins.csv
```

## Build and start

```bash
docker compose build
docker compose up airflow-init
docker compose up -d
docker compose ps
```

Airflow: <http://localhost:8080>

```text
user: airflow
password: airflow
```

API documentation: <http://localhost:8000/docs>

## Run the pipeline

Trigger `penguins_pipeline` in the Airflow UI, or run:

```bash
docker compose exec airflow-scheduler airflow dags trigger penguins_pipeline
```

Other DAGs:

```text
check_mysql_connection
clear_mysql
step_sequence
```

## MySQL: first create database and grant access

```bash
docker compose exec mysql mysql -u root -p
```

```text
password: root_password
```

```sql
CREATE DATABASE IF NOT EXISTS palmerpenguins;
GRANT ALL PRIVILEGES ON palmerpenguins.* TO 'airflow_user'@'%';
FLUSH PRIVILEGES;
exit
```

## MySQL: view penguin data

```bash
docker compose exec mysql mysql -u airflow_user -p -D palmerpenguins
```

```text
password: airflow_password
```

```sql
SHOW TABLES;
SELECT COUNT(*) FROM penguins;
SELECT * FROM penguins LIMIT 10;

SELECT COUNT(*) FROM penguins_clean;
SELECT * FROM penguins_clean LIMIT 10;
exit
```

## API

```bash
curl http://localhost:8000/health
curl http://localhost:8000/models
```

```bash
curl -X POST http://localhost:8000/models/select \
  -H 'Content-Type: application/json' \
  -d '{"model_name":"random_forest"}'
```

```bash
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"island":"Torgersen","bill_length_mm":39.1,"bill_depth_mm":18.7,"flipper_length_mm":181,"body_mass_g":3750,"sex":"MALE"}'
```

## Docker volumes

```bash
docker volume ls
docker volume inspect assignment3_mysql-db-volume
docker volume inspect assignment3_postgres-db-volume
```

## Stop

```bash
docker compose down
```

## Delete Assignment 3 database volumes

```bash
docker compose down -v
```

## Delete all Docker containers, images and volumes

```bash
docker ps -aq | xargs -r docker rm -f
docker images -q | sort -u | xargs -r docker rmi -f
docker volume ls -q | xargs -r docker volume rm -f
```

## Demo

![API demo](files/Demo.gif)