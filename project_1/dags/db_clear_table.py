"""Delete all sample rows while keeping the table definition."""

from datetime import datetime, timezone

from airflow.sdk import DAG, task

from common.postgres import clear_table


with DAG(
    dag_id="db_clear_cover_samples_table",
    description="Truncate the Cover Type table.",
    start_date=datetime(2026, 9, 22, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    tags=["database"],
):

    @task
    def clear_cover_samples_table():
        clear_table()
        print("Table cover_samples cleared.")

    clear_cover_samples_table()
