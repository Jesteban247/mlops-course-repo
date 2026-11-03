# Keep these functions consistent with the pipeline walkthrough notebook.
from .settings import database_url, s3_client
from .preprocessing import prepare_records, normalize_features, SPLIT_STRATEGY
from .training import make_pipeline, metrics, score_predictions

import io, json, os, pathlib
import pandas as pd
from sqlalchemy import create_engine, text
BUCKET='diabetes-source'
MODEL_SCHEMA_VERSION='patient_split_categorical_v2'

def engine(): return create_engine(database_url(),pool_pre_ping=True)

def init_schema(sql_path=None):
    if sql_path is None:
        sql_path = pathlib.Path(__file__).resolve().parents[2] / 'sql' / '01_schema.sql'
    else:
        sql_path = pathlib.Path(sql_path)
    # The SQL file is mounted under /opt/airflow/src/../sql for Airflow.
    if not sql_path.exists(): sql_path=pathlib.Path('/opt/airflow/sql/01_schema.sql')
    with engine().begin() as conn:
        for stmt in sql_path.read_text().split(';'):
            if stmt.strip(): conn.execute(text(stmt))

def next_batch():
    s3=s3_client()
    resp=s3.list_objects_v2(Bucket=BUCKET,Prefix='batches/')
    keys=sorted(x['Key'] for x in resp.get('Contents',[]) if x['Key'].endswith('.csv'))
    with engine().connect() as conn:
        done={r[0] for r in conn.execute(text("SELECT batch_id FROM audit.ingestion_batches WHERE status='completed'"))}
    for key in keys:
        batch=key.rsplit('/',1)[-1].removesuffix('.csv')
        if batch not in done: return {'key':key,'batch_id':batch}
    return None

def ensure_registry_compatible():
    """Reject legacy model versions before ingesting a new batch."""
    import mlflow
    from mlflow.tracking import MlflowClient
    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow-mlflow.mlops-project.svc.cluster.local:5000'))
    client = MlflowClient()
    required = {'feature_schema', 'cohort', 'algorithm', 'created_batch', 'training_batches'}
    incompatible = []
    for version in client.search_model_versions("name='diabetes-readmission'"):
        if required.issubset(version.tags) and version.tags['feature_schema'] == MODEL_SCHEMA_VERSION:
            continue
        run = client.get_run(version.run_id) if version.run_id else None
        params = run.data.params if run else {}
        if params.get('feature_schema') == MODEL_SCHEMA_VERSION and all(params.get(k) for k in ('cohort', 'algorithm', 'batch', 'training_batches')):
            continue  # The training step can recover tags after an interrupted registration.
        incompatible.append(str(version.version))
    if incompatible:
        raise ValueError('Existing model versions use the previous feature schema: '
                         + ', '.join(incompatible) + '. Reset the project before ingesting the next batch.')

def ingest(item):
    if not item: return None
    s3=s3_client()
    body=s3.get_object(Bucket=BUCKET,Key=item['key'])['Body'].read()
    # Keep raw CSV field values as strings; do not replace missing-value markers.
    frame=pd.read_csv(io.BytesIO(body),dtype=str,keep_default_na=False)
    if frame.empty or len(frame)>15000: raise ValueError('Batch must contain 1 to 15,000 rows')
    required={'encounter_id','patient_nbr','readmitted'}
    if not required.issubset(frame.columns): raise ValueError(f'Missing columns: {required-set(frame.columns)}')
    for column in ('encounter_id','patient_nbr'):
        if not frame[column].str.fullmatch(r'\d+').all(): raise ValueError(f'Invalid {column}')
    if frame.encounter_id.map(int).duplicated().any(): raise ValueError('Duplicate encounter within source batch')
    # One transaction prevents partial batches from becoming completed.
    with engine().begin() as conn:
        status=conn.execute(text('SELECT status FROM audit.ingestion_batches WHERE batch_id=:b FOR UPDATE'),{'b':item['batch_id']}).scalar()
        if status == 'completed':
            raise ValueError(f"Batch already completed: {item['batch_id']}; discover the next batch instead")
        conn.execute(text("INSERT INTO audit.ingestion_batches (batch_id,source_key,status) VALUES (:b,:s,'processing') ON CONFLICT (batch_id) DO UPDATE SET status='processing',started_at=now(),completed_at=NULL"),{'b':item['batch_id'],'s':item['key']})
        conn.execute(text('DELETE FROM clean.encounters WHERE batch_id=:b'),{'b':item['batch_id']})
        conn.execute(text('DELETE FROM raw.encounters WHERE batch_id=:b'),{'b':item['batch_id']})
        rows=[{'e':int(r['encounter_id']),'p':int(r['patient_nbr']),'b':item['batch_id'],'s':item['key'],'o':json.dumps(r,default=str)} for r in frame.to_dict(orient='records')]
        # Protect the unique encounter key from duplicate inserts across batches.
        collisions=conn.execute(text('SELECT count(*) FROM raw.encounters WHERE encounter_id = ANY(:ids)'),{'ids':[r['e'] for r in rows]}).scalar()
        if collisions: raise ValueError(f'{collisions} encounter IDs already ingested from another batch')
        conn.execute(text('INSERT INTO raw.encounters(encounter_id,patient_nbr,batch_id,source_key,original) VALUES (:e,:p,:b,:s,CAST(:o AS jsonb))'),rows)
        conn.execute(text("UPDATE audit.ingestion_batches SET row_count=:n WHERE batch_id=:b"),{'n':len(rows),'b':item['batch_id']})
    return item

def clean_batch(item):
    if not item: return None
    with engine().begin() as conn:
        rs=conn.execute(text('SELECT original FROM raw.encounters WHERE batch_id=:b ORDER BY encounter_id'),{'b':item['batch_id']}).fetchall()
        df=pd.DataFrame([r[0] for r in rs])
        if df.empty: raise ValueError('Empty source batch')
        meta, features=prepare_records(df)
        items=[]
        for i,row in meta.iterrows():
            f={k:(None if pd.isna(v) else v) for k,v in features.loc[i].items()}
            items.append({'e':int(row.encounter_id),'p':int(row.patient_nbr),'b':item['batch_id'],'sp':row.split,'y':int(row.target),'f':json.dumps(f,default=str)})
        conn.execute(text('INSERT INTO clean.encounters(encounter_id,patient_nbr,batch_id,split,target,features) VALUES (:e,:p,:b,:sp,:y,CAST(:f AS jsonb)) ON CONFLICT(encounter_id) DO UPDATE SET features=EXCLUDED.features,split=EXCLUDED.split,target=EXCLUDED.target,processed_at=now()'),items)
    return item

def load_clean():
    with engine().connect() as conn:
        rows=conn.execute(text('SELECT encounter_id,batch_id,split,target,features FROM clean.encounters ORDER BY encounter_id')).mappings().all()
    if not rows: raise ValueError('No cleaned training data')
    X=normalize_features(pd.DataFrame([r['features'] for r in rows]))
    return rows,X

def evaluate_model(model, X, table, metadata):
    """Evaluate one fitted model on each batch/split and on pooled splits."""
    predictions = model.predict(X)
    positive_column = list(model.classes_).index(1)
    probabilities = model.predict_proba(X)[:, positive_column]
    y = table['target'].to_numpy()
    batch_ids = sorted(table['batch_id'].unique())
    trained = set(metadata['training_batches'])
    results = []
    for split in ('train', 'validation', 'test'):
        for batch in batch_ids + ['all']:
            mask = table['split'].eq(split)
            if batch != 'all':
                mask &= table['batch_id'].eq(batch)
            mask = mask.to_numpy()
            if not mask.any():
                continue
            seen = None
            if split == 'train':
                seen = ('yes' if batch in trained else 'no') if batch != 'all' else (
                    'yes' if set(batch_ids).issubset(trained) else 'mixed')
            scores = score_predictions(y[mask], predictions[mask], probabilities[mask])
            results.append({**metadata, 'training_batches': ','.join(metadata['training_batches']),
                            'split': split, 'evaluation_batch': batch,
                            'training_rows_seen': seen, **scores})
    return results

def train_and_compare(item):
    """Train candidates, compare all compatible versions and promote by validation ROC-AUC."""
    if not item:
        return {'message': 'No pending batch; skipped training.'}
    import gc
    import mlflow
    import mlflow.sklearn
    from mlflow.exceptions import MlflowException
    from mlflow.tracking import MlflowClient
    from mlflow.models import infer_signature
    from sklearn.metrics import ConfusionMatrixDisplay, RocCurveDisplay, PrecisionRecallDisplay
    import matplotlib.pyplot as plt

    registered_name = 'diabetes-readmission'
    schema_version = MODEL_SCHEMA_VERSION
    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI', 'http://mlflow-mlflow.mlops-project.svc.cluster.local:5000'))
    mlflow.set_experiment('diabetes-pipeline')
    client = MlflowClient()
    versions = list(client.search_model_versions(f"name='{registered_name}'"))
    required_tags = {'feature_schema', 'cohort', 'algorithm', 'created_batch', 'training_batches'}
    incompatible = []
    for version in versions:
        if required_tags.issubset(version.tags) and version.tags['feature_schema'] == schema_version:
            continue
        # A retry may find a version registered just before a tag write failed.
        run = client.get_run(version.run_id) if version.run_id else None
        params = run.data.params if run else {}
        if params.get('feature_schema') != schema_version or not all(params.get(k) for k in ('cohort', 'algorithm', 'batch', 'training_batches')):
            incompatible.append(str(version.version))
            continue
        recovered = {'feature_schema': schema_version, 'cohort': params['cohort'],
                     'algorithm': params['algorithm'], 'created_batch': params['batch'],
                     'training_batches': json.dumps(params['training_batches'].split(','))}
        for tag, value in recovered.items():
            client.set_model_version_tag(registered_name, str(version.version), tag, value)
    if incompatible:
        raise ValueError('Existing model versions use the previous feature schema: '
                         + ', '.join(incompatible) + '. Reset the project before the clean run.')
    versions = list(client.search_model_versions(f"name='{registered_name}'"))

    rows, X = load_clean()
    table = pd.DataFrame([{'batch_id': r['batch_id'], 'split': r['split'], 'target': r['target']} for r in rows])
    y = table['target']
    train = table['split'].eq('train')
    validation = table['split'].eq('validation')
    latest = table['batch_id'].eq(item['batch_id'])
    if y[train].nunique() < 2 or y[validation].nunique() < 2:
        raise ValueError('Accumulated train and validation must each contain both target classes for ROC-AUC.')

    cohorts = [('cumulative', train)]
    if not (train & latest).equals(train):
        cohorts.insert(0, ('latest_batch', train & latest))
    existing = {(v.tags.get('created_batch'), v.tags.get('cohort'), v.tags.get('algorithm')): v
                for v in versions}
    requirements = ['mlflow==3.17.2', 'scikit-learn==1.7.1', 'numpy==2.2.6',
                    'pandas==2.3.1', 'skops==0.16.0']

    for cohort, mask in cohorts:
        if mask.sum() < 30 or y[mask].nunique() < 2:
            raise ValueError(f'Insufficient training rows or target classes for {cohort}.')
        training_batches = sorted(table.loc[mask, 'batch_id'].unique())
        for algorithm in ('logistic', 'forest'):
            key = (item['batch_id'], cohort, algorithm)
            if key in existing:
                print(f'Reusing registered version {existing[key].version} for {key}')
                continue
            print(f'Training {cohort} / {algorithm} on {int(mask.sum())} rows')
            model = make_pipeline(X.loc[mask], algorithm)
            model.fit(X.loc[mask], y.loc[mask])
            metadata = {'version': 'pending', 'algorithm': algorithm, 'cohort': cohort,
                        'created_batch': item['batch_id'], 'training_batches': training_batches}
            evaluation = evaluate_model(model, X, table, metadata)
            in_sample = metrics(model, X.loc[mask], y.loc[mask])
            with mlflow.start_run(run_name=f"{item['batch_id']}-{cohort}-{algorithm}"):
                mlflow.log_params({'cohort': cohort, 'algorithm': algorithm,
                                   'batch': item['batch_id'], 'train_rows': int(mask.sum()),
                                   'training_batches': ','.join(training_batches),
                                   'split_strategy': SPLIT_STRATEGY,
                                   'selection_metric': 'accumulated_validation_roc_auc',
                                   'feature_schema': schema_version})
                model_params = {f'model_{k}': str(v) for k, v in model.named_steps['model'].get_params(deep=False).items()}
                mlflow.log_params(model_params)
                mlflow.log_metrics({f'train_in_sample_{k}': v for k, v in in_sample.items() if v is not None})
                for split in ('validation', 'test'):
                    aggregate = next((r for r in evaluation if r['split'] == split and r['evaluation_batch'] == 'all'), None)
                    if aggregate:
                        mlflow.log_metrics({f'{split}_{k}': aggregate[k] for k in (
                            'n', 'positive', 'negative', 'tn', 'fp', 'fn', 'tp',
                            'accuracy', 'precision', 'recall', 'f1', 'roc_auc', 'pr_auc')
                            if aggregate[k] is not None})
                fig, axes = plt.subplots(1, 3, figsize=(15, 4))
                ConfusionMatrixDisplay.from_estimator(model, X.loc[validation], y.loc[validation], ax=axes[0])
                RocCurveDisplay.from_estimator(model, X.loc[validation], y.loc[validation], ax=axes[1])
                PrecisionRecallDisplay.from_estimator(model, X.loc[validation], y.loc[validation], ax=axes[2])
                fig.tight_layout()
                mlflow.log_figure(fig, 'evaluation/validation_plots.png')
                plt.close(fig)
                signature = infer_signature(X.loc[mask].head(10), model.predict(X.loc[mask].head(10)))
                info = mlflow.sklearn.log_model(model, name='model', signature=signature,
                    registered_model_name=registered_name, pip_requirements=requirements,
                    skops_trusted_types=['numpy.dtype', 'sklearn.tree._tree.Tree'])
                if info.registered_model_version is None:
                    raise RuntimeError('MLflow did not return a registered model version.')
                for row in evaluation:
                    row['version'] = str(info.registered_model_version)
                mlflow.log_dict({'rows': evaluation}, 'evaluation/metrics_by_batch.json')
                for tag, value in {'feature_schema': schema_version, 'cohort': cohort,
                                   'algorithm': algorithm, 'created_batch': item['batch_id'],
                                   'training_batches': json.dumps(training_batches)}.items():
                    client.set_model_version_tag(registered_name, str(info.registered_model_version), tag, value)
                print(f'Registered {registered_name} version {info.registered_model_version}')
            del model
            gc.collect()

    try:
        champion_before = str(client.get_model_version_by_alias(registered_name, 'champion').version)
    except MlflowException as exc:
        if exc.error_code != 'RESOURCE_DOES_NOT_EXIST' and 'registered model alias champion not found' not in str(exc).lower():
            raise
        champion_before = None

    all_rows = []
    for version in client.search_model_versions(f"name='{registered_name}'"):
        tags = version.tags
        if tags.get('feature_schema') != schema_version:
            raise ValueError(f'Incompatible model version {version.version}; reset before comparing.')
        metadata = {'version': str(version.version), 'algorithm': tags['algorithm'],
                    'cohort': tags['cohort'], 'created_batch': tags['created_batch'],
                    'training_batches': json.loads(tags['training_batches'])}
        print(f'Evaluating version {version.version} on all available splits')
        model = mlflow.sklearn.load_model(f'models:/{registered_name}/{version.version}')
        all_rows.extend(evaluate_model(model, X, table, metadata))
        del model
        gc.collect()

    scores = pd.DataFrame(all_rows)
    ranking = scores[(scores['split'] == 'validation') & (scores['evaluation_batch'] == 'all') & scores['roc_auc'].notna()]
    if ranking.empty:
        raise ValueError('No model has a defined ROC-AUC on accumulated validation.')
    best_score = float(ranking['roc_auc'].max())
    tied = ranking[ranking['roc_auc'] == best_score]
    if champion_before is not None and champion_before in tied['version'].tolist():
        champion_after = champion_before
    else:
        champion_after = str(tied.sort_values('version', key=lambda col: col.astype(int)).iloc[0]['version'])

    with mlflow.start_run(run_name=f"{item['batch_id']}-comparison") as run:
        mlflow.log_params({'batch': item['batch_id'], 'selection_metric': 'accumulated_validation_roc_auc',
                           'selection_split': 'validation', 'split_strategy': SPLIT_STRATEGY,
                           'champion_before': champion_before or 'none', 'champion_after': champion_after})
        mlflow.log_metric('selected_validation_roc_auc', best_score)
        mlflow.log_dict({'rows': all_rows}, 'evaluation/metrics.json')
        mlflow.log_text(scores.to_csv(index=False), 'evaluation/metrics.csv')
        by_batch = scores[(scores['split'] == 'validation') & (scores['evaluation_batch'] != 'all')]
        if not by_batch.empty and by_batch['roc_auc'].notna().any():
            plot_data = by_batch.pivot(index='evaluation_batch', columns='version', values='roc_auc')
            ax = plot_data.plot.bar(figsize=(10, 4), ylim=(0, 1), rot=0)
            ax.set_ylabel('Validation ROC-AUC'); ax.set_title('Model versions by batch')
            ax.figure.tight_layout()
            mlflow.log_figure(ax.figure, 'evaluation/validation_roc_auc_by_batch.png')
            plt.close(ax.figure)
        comparison_run_id = run.info.run_id

    if champion_after != champion_before:
        client.set_registered_model_alias(registered_name, 'champion', champion_after)
    print(f'Champion version {champion_after}; accumulated validation ROC-AUC={best_score:.4f}')
    return {'batch_id': item['batch_id'], 'champion_before': champion_before,
            'champion_after': champion_after, 'selection_metric': 'validation_roc_auc',
            'validation_roc_auc': best_score, 'comparison_run_id': comparison_run_id,
            'models_compared': int(ranking.shape[0])}

def finish_batch(item):
    """Only mark the batch complete after ingestion, cleaning and training succeed."""
    if not item: return None
    with engine().begin() as conn:
        result=conn.execute(text("UPDATE audit.ingestion_batches SET status='completed',completed_at=now() WHERE batch_id=:b AND status='processing'"),{'b':item['batch_id']})
        if result.rowcount != 1:
            status=conn.execute(text('SELECT status FROM audit.ingestion_batches WHERE batch_id=:b'),{'b':item['batch_id']}).scalar()
            if status != 'completed': raise ValueError(f"Batch is not processing: {item['batch_id']}")
    return item
