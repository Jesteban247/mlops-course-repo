import logging
import json
import os
import socket
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from mlflow.tracking import MlflowClient
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, text

from diabetes.preprocessing import normalize_features
from diabetes.settings import database_url

logger = logging.getLogger('uvicorn.error')
MODEL_NAME = 'diabetes-readmission'
INSTANCE = socket.gethostname()
API_NAME = os.getenv('API_NAME', 'diabetes-api')
_state_lock = threading.Lock()
_reload_lock = threading.Lock()
_loaded = None
_engine = None
REQUESTS = Counter('diabetes_predictions_total', 'Prediction requests', ['status'])
LATENCY = Histogram('diabetes_prediction_seconds', 'Prediction request latency in seconds')


def refresh_model():
    """Keep the current model available until the new version is loaded."""
    global _loaded
    with _reload_lock:
        client = MlflowClient()
        version = str(client.get_model_version_by_alias(MODEL_NAME, 'champion').version)
        with _state_lock:
            current = _loaded
        if current and current['version'] == version:
            return version
        model = mlflow.sklearn.load_model(f'models:/{MODEL_NAME}/{version}')
        if not hasattr(model, 'feature_names_in_') or not hasattr(model, 'predict_proba'):
            raise ValueError('Champion must provide feature names and probabilities')
        with _state_lock:
            _loaded = {'model': model, 'version': version}
        logger.info('Loaded champion %s version %s', MODEL_NAME, version)
        return version


@asynccontextmanager
async def lifespan(app):
    global _engine
    mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])
    _engine = create_engine(database_url(), pool_pre_ping=True)
    try:
        refresh_model()
    except Exception:
        logger.exception('No champion is available at startup')
    stop = threading.Event()
    interval = int(os.getenv('MODEL_REFRESH_SECONDS', '0'))
    def check_champion():
        while not stop.wait(interval):
            try:
                refresh_model()
            except Exception:
                logger.exception('Champion check failed; keeping the current model')
    worker = None
    if interval > 0:
        worker = threading.Thread(target=check_champion, daemon=True)
        worker.start()
    yield
    stop.set()
    if worker:
        worker.join(timeout=2)
    _engine.dispose()


app = FastAPI(title='Diabetes readmission API', lifespan=lifespan)


@app.middleware('http')
async def prediction_metrics(request, call_next):
    if request.url.path != '/predict':
        return await call_next(request)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        REQUESTS.labels(status='500').inc()
        raise
    else:
        REQUESTS.labels(status=str(response.status_code)).inc()
        return response
    finally:
        LATENCY.observe(time.perf_counter() - started)


@app.get('/metrics')
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class PredictionRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        'example': json.loads((Path(__file__).parent / 'example-request.json').read_text())
    })
    instances: list[dict] = Field(min_length=1, max_length=100)


@app.get('/health')
def health():
    return {'status': 'ok', 'instance': INSTANCE}


@app.get('/ready')
def ready():
    with _state_lock:
        state = _loaded
    if state is None:
        raise HTTPException(503, 'No champion loaded')
    return {'status': 'ready', 'model_name': MODEL_NAME, 'model_version': state['version']}


@app.get('/model-info')
def model_info():
    with _state_lock:
        state = _loaded
    if state is None:
        raise HTTPException(503, 'No champion loaded')
    return {'status': 'ready', 'api_name': API_NAME, 'model_name': MODEL_NAME, 'model_version': state['version'], 'instance': INSTANCE}


@app.post('/internal/reload')
def reload_champion():
    try:
        version = refresh_model()
    except Exception as exc:
        logger.exception('Champion reload failed; keeping the current model')
        raise HTTPException(503, 'Champion reload failed; existing model retained') from exc
    return {'model_name': MODEL_NAME, 'model_version': version, 'instance': INSTANCE}


@app.post('/predict')
def predict(request: PredictionRequest):
    start = time.perf_counter()
    with _state_lock:
        state = _loaded
    if state is None:
        raise HTTPException(503, 'No champion loaded; train a batch first')
    model = state['model']
    expected = list(model.feature_names_in_)
    for index, row in enumerate(request.instances):
        missing, extra = sorted(set(expected) - row.keys()), sorted(row.keys() - set(expected))
        if missing or extra:
            raise HTTPException(422, {'row': index, 'missing_features': missing, 'unexpected_features': extra})
    try:
        frame = normalize_features(pd.DataFrame(request.instances, columns=expected))
        predictions = model.predict(frame)
        probabilities = model.predict_proba(frame)
        positive_index = list(model.classes_).index(1)
        results = [{'prediction': int(pred), 'probability_readmitted_within_30_days': float(probs[positive_index])}
                   for pred, probs in zip(predictions, probabilities)]
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, f'Invalid features: {exc}') from exc
    request_id = str(uuid.uuid4())
    response = {'request_id': request_id, 'api_name': API_NAME, 'model_name': MODEL_NAME, 'model_version': state['version'],
                'instance': INSTANCE, 'predictions': results}
    try:
        with _engine.begin() as conn:
            conn.execute(text('INSERT INTO audit.inference_logs (request_id,payload,prediction,model_name,model_version,response_ms) '
                              'VALUES (:id,CAST(:payload AS jsonb),CAST(:prediction AS jsonb),:name,:version,:ms)'),
                         {'id': request_id, 'payload': json.dumps(request.model_dump()),
                          'prediction': json.dumps(results), 'name': MODEL_NAME, 'version': state['version'],
                          'ms': (time.perf_counter() - start) * 1000})
    except Exception:
        logger.exception('Could not save inference audit record')
        raise HTTPException(503, 'Could not save inference audit record')
    response['processing_time_ms'] = round((time.perf_counter() - start) * 1000, 2)
    return response
