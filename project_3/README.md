# Project 3 — Property price MLOps

Group 4 property batches are processed in Airflow, stored in PostgreSQL, and used to train an XGBoost candidate. MLflow tracks the candidate and a `champion` alias; MinIO stores artifacts. FastAPI loads the champion without rebuilding its image.

## Workflow

1. Fetch one batch, save its original response and raw rows, then validate and clean it.
2. Compare accumulated valid data with the last training data and decide whether to train.
3. Train XGBoost and compare candidate and champion MAE on the same validation split.
4. Promote only a lower-MAE candidate; record the decision and version.
5. Store each batch decision and distribution plots in a separate MinIO report bucket.
6. Serve predictions through `/predict`; `/health` checks the process, `/ready` checks the loaded model, and `/metrics` exposes Prometheus metrics.
7. Streamlit displays predictions and batch history; Prometheus, Grafana, Locust and the API HPA support load testing.

The target is the dataset's `price`, which can be a listing or a recent sale price. The selected model excludes `status` and `prev_sold_date`. Splits use a stable street/city/state proxy; it is not a verified property identifier. The thresholds are experimental, and data validation and real-world performance need further review.

Notebook 01 fetches data only when explicitly enabled. Notebooks 02–08 explore the saved batches and decisions; notebook 09 inspects the database. The selected preprocessing and XGBoost implementation are shared in `src/property_ml`.

## Files

```text
api/              FastAPI code, image, and example request
streamlit/        Prediction and batch history interface
locust/           Local and Kubernetes load test
argocd/           Argo CD applications
dags/             Airflow task and branch definitions
k8s/              Component manifests and Airflow Helm values
notebooks/        Exploration and database inspection
sql/              Raw, clean, and audit schemas
src/property_ml/  Ingestion, decisions, features, and training functions
tests/            Pytest checks
data/             Local batches and staged responses, excluded from Git
```

Setup, testing, and cleanup for both machines are in [commands.md](commands.md). The `.env` file and downloaded batches are private and excluded from Git. Airflow reads shared files from NBAM07; commit the code and update the NBAM07 checkout and `CODE_VERSION` Secret before a reproducible run. Its published Airflow image installs pinned dependencies on scheduler startup. The API image is built by GitHub Actions and deployed through Argo CD.

A fetch failure is not retried automatically: the source may already have advanced. Complete responses are staged under `data/ingestion` and reused for the same DAG run after a database failure. Inspect any `.partial` file and source state before retrying an incomplete fetch. MLflow models use cloudpickle; load models only from the trusted project registry.

The MinIO `project-3-batch-reports` bucket contains a JSON report and numerical plots per new decision. PostgreSQL stores the report key and remains the source of batch history. MLflow retains model and training artifacts in its own bucket. Older batches processed before reporting was enabled do not automatically gain reports.

Prometheus discovers API pods individually; Grafana shows request rate by pod, latency, errors, and process resources. HPA scales the API based on CPU and Argo CD ignores the HPA-managed replica field. Locust can run inside Kubernetes or on NBAM07 through the Kubernetes Service; a port-forward to the Service reaches a single pod.
