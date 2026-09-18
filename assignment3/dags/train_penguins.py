from airflow.sdk import dag

@dag(dag_id="train_penguins", schedule=None, catchup=False, tags=["penguins", "training"])
def train_penguins():
    pass

train_penguins()
