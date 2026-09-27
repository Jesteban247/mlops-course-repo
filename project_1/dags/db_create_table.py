"""Create the Cover Type samples table."""

from datetime import datetime, timezone

from airflow.sdk import DAG, task

from common.postgres import create_table, inspect_table


with DAG(
    dag_id="db_create_cover_samples_table",
    description="Create the PostgreSQL table used by the API extraction DAG.",
    start_date=datetime(2026, 9, 22, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    tags=["database"],
):

    @task
    def create_cover_samples_table():
        create_table()
        details = inspect_table()
        print(f"Created table cover_samples with {len(details['columns'])} columns.")
        print(f"Columns: {details['columns']}")

    create_cover_samples_table()
