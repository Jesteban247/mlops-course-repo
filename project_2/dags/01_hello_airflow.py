import pendulum
from airflow.sdk import dag, task


@dag(
    dag_id="hello_mlops",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    tags=["mlops", "test"],
)
def hello_mlops():
    @task
    def start():
        print("Hello from Airflow!")

    start()


hello_mlops()
