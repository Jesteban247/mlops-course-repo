import os, sys
import pendulum
from airflow.sdk import dag,task,get_current_context
sys.path.insert(0,'/opt/airflow/src')

@dag(dag_id='03_reset_pipeline',schedule=None,start_date=pendulum.datetime(2026,1,1,tz='UTC'),catchup=False,max_active_runs=1,tags=['development','destructive'])
def reset():
    @task
    def reset_dev():
        from sqlalchemy import text
        from diabetes.pipeline import engine
        context=get_current_context(); conf=context['dag_run'].conf or {}
        if conf.get('confirm_reset') != 'RESET_DEV_DATA':
            raise ValueError('Explicitly pass {"confirm_reset":"RESET_DEV_DATA"} to clear development data.')
        if conf.get('reset_mlflow') is True and conf.get('confirm_mlflow') != 'DELETE_DIABETES_MLFLOW':
            raise ValueError('For MLflow reset also supply confirm_mlflow=DELETE_DIABETES_MLFLOW')
        # Never delete the source MinIO buckets, Airflow metadata, or MLflow postgres.
        with engine().begin() as con:
            con.execute(text('TRUNCATE clean.encounters,raw.encounters,audit.ingestion_batches'))
        print('Application raw/clean/batch ledger cleared. MinIO source preserved.')
        if conf.get('reset_mlflow') is True:
            import mlflow
            from mlflow.tracking import MlflowClient
            mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI','http://mlflow-mlflow.mlops-project.svc.cluster.local:5000'))
            client=MlflowClient()
            exp=client.get_experiment_by_name('diabetes-pipeline')
            if exp: client.delete_experiment(exp.experiment_id)
            try: client.delete_registered_model('diabetes-readmission')
            except Exception as exc:
                if 'NOT_FOUND' not in str(exc).upper() and 'does not exist' not in str(exc).lower(): raise
            print('Pipeline experiment and registered model deleted in MLflow. Artifacts may remain in MinIO.')
        # MLflow experiment/model registry intentionally NOT deleted automatically.
        # MLflow resets must be reviewed separately to avoid dangling artifacts and aliases.
    reset_dev()
reset()
