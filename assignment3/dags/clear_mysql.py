from airflow.providers.mysql.hooks.mysql import MySqlHook
from airflow.sdk import dag, task


@dag(dag_id="clear_mysql", schedule=None, catchup=False, tags=["mysql", "maintenance"])
def clear_mysql():
    @task
    def clear_tables():
        hook = MySqlHook(mysql_conn_id="palmerpenguins")
        tables = [row[0] for row in hook.get_records("SHOW TABLES")]
        if not tables:
            print("palmerpenguins has no tables; nothing to clear.")
            return

        for table in tables:
            safe_table = table.replace("`", "``")
            hook.run(f"TRUNCATE TABLE `{safe_table}`")
            print(f"Cleared {table}")

    clear_tables()


clear_mysql()
