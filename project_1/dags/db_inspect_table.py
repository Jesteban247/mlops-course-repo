"""Print row count, column count and a five-row preview."""

from datetime import datetime, timezone

from airflow.sdk import DAG, task

from common.postgres import inspect_table


with DAG(
    dag_id="db_inspect_cover_samples_table",
    description="Show Cover Type table dimensions and the first five rows.",
    start_date=datetime(2026, 9, 22, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    tags=["database"],
):

    @task
    def inspect_cover_samples_table():
        details = inspect_table(head_size=5)
        if not details["exists"]:
            print("Table cover_samples does not exist yet.")
            return

        print(f"Rows: {details['row_count']}")
        print(f"Columns ({len(details['columns'])}): {details['columns']}")
        print(f"Head (up to 5 rows): {details['head']}")
        if details["row_count"] == 0:
            print("Table exists and is empty.")

    inspect_cover_samples_table()
