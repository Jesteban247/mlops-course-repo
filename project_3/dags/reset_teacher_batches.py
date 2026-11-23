"""Manually reset the teacher's batch sequence for our group."""
import os

import pendulum
from airflow.sdk import dag, task


@dag(dag_id='project_3_reset_teacher_batches', schedule=None,
     start_date=pendulum.datetime(2026, 1, 1, tz='UTC'), catchup=False,
     max_active_runs=1, default_args={'retries': 0}, tags=['project-3'])
def reset_teacher_batches():
    @task
    def reset_batches():
        import requests

        url = os.environ['DATA_API_URL'].rstrip('/') + '/restart_data_generation'
        group = int(os.environ['DATA_API_GROUP'])
        response = requests.get(url, params={'group_number': group}, timeout=30)
        response.raise_for_status()
        print(f'Group {group} reset: {response.text}')

    reset_batches()


reset_teacher_batches()
