"""Manually check that the course API is reachable."""

from datetime import datetime, timezone

from airflow.sdk import DAG, task

from common.api_client import API_BASE_URL, check_api


with DAG(
    dag_id="api_connection_check",
    description="Check the course API root endpoint without requesting data.",
    start_date=datetime(2026, 9, 22, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    tags=["api"],
):

    @task
    def check_connection():
        result = check_api()
        print(f"API reachable at {API_BASE_URL}; response: {result}")

    check_connection()
