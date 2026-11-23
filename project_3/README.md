# Project 3 — Property price MLOps

Group 4 property batches are processed in Airflow, stored in PostgreSQL, and used to train an XGBoost candidate. MLflow tracks the candidate and a `champion` alias; MinIO stores artifacts. FastAPI loads the champion without rebuilding its image.

## Workflow

1. Fetch one batch, save its original response and raw rows, then validate and clean it.
2. Compare accumulated valid data with the last training data and decide whether to train.
3. Train XGBoost and compare candidate and champion MAE on the same validation split.
4. Promote only a lower-MAE candidate; record the decision and version.
5. Serve predictions through `/predict`; `/health` checks the process and `/ready` checks the loaded model.

The target is the dataset's `price`, which can be a listing or a recent sale price. The selected model excludes `status` and `prev_sold_date`. Splits use a stable street/city/state proxy; it is not a verified property identifier. The thresholds are experimental, and data validation and real-world performance need further review.

Notebook 01 fetches data only when explicitly enabled. Notebooks 02–08 explore the saved batches and decisions; notebook 09 inspects the database. The selected preprocessing and XGBoost implementation are shared in `src/property_ml`.

## Files

```text
api/              FastAPI code, image, and example request
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
