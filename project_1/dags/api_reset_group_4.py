"""Manually reset the server-side batch counter for group 4."""

from datetime import datetime, timezone

from airflow.sdk import DAG, task

from common.api_client import reset_group
from common.settings import GROUP_NUMBER


with DAG(
    dag_id="api_reset_group_4",
    description="Reset the API batch counter for group 4.",
    start_date=datetime(2026, 9, 22, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    tags=["api"],
):

    @task
    def reset_group_4():
        result = reset_group(GROUP_NUMBER)
        print(f"Group {GROUP_NUMBER}: reset response {result}")

    reset_group_4()
