"""Process one group 4 batch per run and branch on training and promotion."""
import sys
import pendulum
from airflow.sdk import dag, task, get_current_context

sys.path.insert(0, '/opt/airflow/src')


@dag(dag_id='project_3_property_pipeline', schedule=None,
     start_date=pendulum.datetime(2026, 1, 1, tz='UTC'), catchup=False,
     max_active_runs=1, default_args={'retries': 0}, tags=['project-3'])
def property_pipeline():
    @task
    def initialize():
        from property_ml.ingestion import initialize as run
        run()

    @task
    def fetch_batch():
        from property_ml.ingestion import fetch_and_store
        return fetch_and_store(get_current_context()['run_id'])

    @task
    def validate_and_clean(batch):
        from property_ml.ingestion import clean_batch
        return clean_batch(batch)

    @task.branch
    def decide_training(batch):
        from property_ml.batch_decisions import decide_batch
        decision = decide_batch(batch, get_current_context()['run_id'])
        return 'train_candidate' if decision == 'train' else 'skip_training'

    @task
    def skip_training():
        print('Batch saved; accumulating data for a later decision.')

    @task
    def train_candidate(batch):
        from property_ml.training import train_candidate as run
        return run(batch)

    @task
    def compare_with_champion(candidate):
        from property_ml.training import compare_candidate
        return compare_candidate(candidate)

    @task.branch
    def decide_promotion(result):
        return 'promote_model' if result['promoted'] else 'reject_model'

    @task
    def promote_model(result):
        from property_ml.training import record_model_decision
        return record_model_decision(result)

    @task
    def reject_model(result):
        from property_ml.training import record_model_decision
        return record_model_decision(result)

    ready = initialize()
    batch = fetch_batch()
    ready >> batch
    prepared = validate_and_clean(batch)
    branch = decide_training(prepared)
    candidate = train_candidate(prepared)
    branch >> [candidate, skip_training()]
    comparison = compare_with_champion(candidate)
    promotion = decide_promotion(comparison)
    promotion >> [promote_model(comparison), reject_model(comparison)]


property_pipeline()
