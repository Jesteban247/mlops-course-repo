from airflow.providers.mysql.hooks.mysql import MySqlHook
from airflow.sdk import dag, task

@dag(dag_id="check_mysql_connection", schedule=None, catchup=False, tags=["test", "mysql"])
def check_mysql_connection():
    @task
    def check_mysql():
        print(f"MySQL connection works: {MySqlHook(mysql_conn_id='mysql').get_first('SELECT 1')[0]}")
    check_mysql()

check_mysql_connection()
