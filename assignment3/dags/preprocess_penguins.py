from airflow.sdk import dag

@dag(dag_id="preprocess_penguins", schedule=None, catchup=False, tags=["penguins", "preprocessing"])
def preprocess_penguins():
    pass

preprocess_penguins()
