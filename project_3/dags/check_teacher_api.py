"""Check the teacher's API without requesting a batch."""
import os

import pendulum
from airflow.sdk import dag, task


@dag(dag_id='project_3_check_teacher_api', schedule=None,
     start_date=pendulum.datetime(2026, 1, 1, tz='UTC'), catchup=False,
     max_active_runs=1, default_args={'retries': 0}, tags=['project-3'])
def check_teacher_api():
    @task
    def check_health():
        import requests

        url = os.environ['DATA_API_URL'].rstrip('/') + '/health'
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        print(f'API health: {response.text}')

    check_health()


check_teacher_api()
