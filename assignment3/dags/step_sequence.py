from airflow.sdk import dag, task

@dag(dag_id="step_sequence", schedule=None, catchup=False, tags=["test"])
def step_sequence():
    @task
    def say(step): print(f"Hi from step {step}")
    say(1) >> say(2) >> [say(3), say(4)] >> say(5)

step_sequence()
