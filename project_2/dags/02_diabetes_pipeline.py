import os, sys
import pendulum
from airflow.sdk import dag, task
sys.path.insert(0,'/opt/airflow/src')

@dag(dag_id='02_diabetes_pipeline',schedule=None,start_date=pendulum.datetime(2026,1,1,tz='UTC'),catchup=False,max_active_runs=1,tags=['diabetes','incremental'])
def diabetes_pipeline():
    @task
    def initialize():
        from diabetes.pipeline import init_schema
        init_schema()
    @task
    def discover():
        from diabetes.pipeline import next_batch
        result=next_batch()
        print(f'Next batch: {result}' if result else 'All source batches already processed.')
        return result
    @task.short_circuit
    def has_new_batch(item):
        return item is not None
    @task
    def check_registry():
        from diabetes.pipeline import ensure_registry_compatible
        ensure_registry_compatible()
    @task
    def ingest(item):
        from diabetes.pipeline import ingest
        return ingest(item)
    @task
    def clean(item):
        from diabetes.pipeline import clean_batch
        return clean_batch(item)
    @task
    def train(item):
        from diabetes.pipeline import train_and_compare
        return train_and_compare(item)
    @task
    def finish(item):
        from diabetes.pipeline import finish_batch
        return finish_batch(item)
    @task
    def notify_api(result):
        import urllib.error
        import urllib.request
        if result.get('champion_before') == result.get('champion_after'):
            print('Champion unchanged; no API reload needed.')
            return
        for name, base in [('test', os.environ['TEST_API_RELOAD_URL']), ('scaled', os.environ['SCALED_API_URL'])]:
            url = f'{base.rstrip("/")}/internal/reload'
            try:
                with urllib.request.urlopen(urllib.request.Request(url, data=b'', method='POST'), timeout=120) as response:
                    print(f'{name} API notified: {response.read().decode()}')
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                print(f'{name} API notification failed: {exc}. Batch remains complete.')
        print('Scaled replicas also check for champion updates every 60 seconds.')
    ready=initialize(); item=discover(); ready >> item
    check=has_new_batch(item)
    registry=check_registry(); check >> registry
    ingested=ingest(item); registry >> ingested
    cleaned=clean(ingested)
    trained=train(cleaned)
    completed=finish(cleaned)
    trained >> completed
    notification=notify_api(trained)
    completed >> notification
diabetes_pipeline()
