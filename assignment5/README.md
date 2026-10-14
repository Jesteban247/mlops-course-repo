# Assignment 5

## Part 1 — Start services (VM)

```bash
cd /home/estudiante/mlops-course-repo/assignment5
cp .env.example .env
docker compose up -d --build --wait
```

## Part 2 — Train the model (Jupyter)

Jupyter — port `8888`:

```text
http://localhost:8888/lab
http://127.0.0.1:8888/lab
http://VM_IP:8888/lab
```

Default token: `assignment5-local` (`JUPYTER_TOKEN` in `.env`).

```text
train_model.ipynb → Run → Run All Cells
```

MLflow — port `5000`, no login:

```text
http://localhost:5000
http://127.0.0.1:5000
http://VM_IP:5000
```

MinIO console — port `9001`:

```text
http://localhost:9001
http://127.0.0.1:9001
http://VM_IP:9001
```

Default username: `assignment5-storage` (`AWS_ACCESS_KEY_ID` in `.env`).

Default password: `assignment5-storage-password` (`AWS_SECRET_ACCESS_KEY` in `.env`).

## Part 3 — Test the local API

Local API — port `8001`:

```text
http://localhost:8001/docs
http://127.0.0.1:8001/docs
http://VM_IP:8001/docs
```

```text
POST /predict → Try it out → Execute
```

## Part 4 — Publish the tested image (VM)

Set `API_IMAGE` in `.env`:

```dotenv
API_IMAGE=YOUR_DOCKERHUB_USER/heart-inference:1.0.0
```

```bash
set -a
source .env
set +a
docker tag assignment5-api:local "$API_IMAGE"
docker login
docker push "$API_IMAGE"
docker compose stop api-test jupyter
```

## Part 5 — Start one replica and Nginx (VM)

```bash
docker compose pull api nginx
docker compose up -d --wait --scale api=1 api nginx
```

Balanced API — port `8000`:

```text
http://localhost:8000/docs
http://127.0.0.1:8000/docs
http://VM_IP:8000/docs
```

Nginx requests:

```bash
docker compose logs -f nginx
```

CPU and memory during the test (another VM terminal):

```bash
docker stats
```

## Part 6 — Prepare Locust (Mac)

Copy only the `locust/` folder to the Mac. Use `VM_IP` from the Mac; `localhost` and `127.0.0.1` refer to the machine where the browser runs.

```bash
cd locust
conda create -n locust python=3.11 pip -y
conda activate locust
python -m pip install --require-hashes -r requirements.txt
cp .env.example .env
```

Set the reachable VM address in this folder's `.env`:

```dotenv
TARGET_HOST=http://VM_IP:8000
```

```bash
python run.py smoke
```

## Part 7 — Measure one replica (Mac)

Each command creates 10 users per second until the requested total, warms up for 15 seconds, then measures for 120 seconds and stops automatically. Users repeatedly send predictions, waiting 0.5–1.5 seconds between requests.

Results are saved automatically in `locust/results/`, with replica count, user count and a timestamp: `*_summary.json`, `*_window.json` and Locust CSV files. Acceptance: failures < 1% and p95 < 500 ms during the measured window; the expected replicas must respond using the same model.

```bash
python run.py load --replicas 1 --users 10 --spawn-rate 1
python run.py load --replicas 1 --users 25 --spawn-rate 1
python run.py load --replicas 1 --users 50 --spawn-rate 1
python run.py load --replicas 1 --users 100 --spawn-rate 1
```

If every level passes, continue increasing users. After the first failing level, try smaller increments between the last passing and first failing levels.

## Part 8 — Switch to three replicas

VM — create missing replicas, keeping the same image and model:

```bash
docker compose up -d --wait --scale api=3 api nginx
```

Mac — allow Docker DNS to refresh, then repeat with the same settings:

```bash
sleep 6
python run.py smoke
python run.py load --replicas 3 --users 10 --spawn-rate 1
python run.py load --replicas 3 --users 25 --spawn-rate 5
python run.py load --replicas 3 --users 50 --spawn-rate 5
python run.py load --replicas 3 --users 100 --spawn-rate 5
```

## Part 9 — Video demo

[![Video demo: MLflow heart disease experiment](files/Demo.png)](https://drive.google.com/file/d/1Rf4WNv328yIbfRgqGWJFz16FwPt615Pf/view?usp=share_link)

Click the image to watch the video.

## Part 10 — Delete everything, including models and metadata (VM)

```bash
docker compose --profile '*' down --volumes --remove-orphans
rm -f deployment/model.env
```
