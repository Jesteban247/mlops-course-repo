import json
import logging
import os
import socket
import threading
import uuid
from contextlib import asynccontextmanager

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mlflow.tracking import MlflowClient
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from property_ml.settings import engine

logger = logging.getLogger('uvicorn.error')
MODEL_NAME = os.getenv('MODEL_NAME', 'property-price')
POD_NAME = os.getenv('POD_NAME', socket.gethostname())
_state_lock = threading.Lock()
_reload_lock = threading.Lock()
_state = None
_db = None


def refresh_model():
    global _state
    with _reload_lock:
        version = str(MlflowClient().get_model_version_by_alias(MODEL_NAME, 'champion').version)
        with _state_lock:
            current = _state
        if current and current['version'] == version:
            return version
        model = mlflow.sklearn.load_model(f'models:/{MODEL_NAME}/{version}')
        with _state_lock:
            _state = {'model': model, 'version': version}
        return version


def record(request_id, payload, prediction, version, status, error=None):
    if _db is None:
        raise RuntimeError('Database is unavailable')
    with _db.begin() as conn:
        conn.execute(text('''INSERT INTO audit.inference_events(request_id,payload,prediction,model_version,pod,status,error)
            VALUES(:id,CAST(:payload AS jsonb),:prediction,:version,:pod,:status,:error)'''),
            {'id':request_id, 'payload':json.dumps(payload), 'prediction':prediction, 'version':version,
             'pod':POD_NAME, 'status':status, 'error':error})


@asynccontextmanager
async def lifespan(app):
    global _db
    mlflow.set_tracking_uri(os.environ['MLFLOW_TRACKING_URI'])
    _db = engine()
    stop = threading.Event()
    interval = max(5, int(os.getenv('MODEL_REFRESH_SECONDS', '60')))
    def watch():
        while not stop.is_set():
            try:
                refresh_model()
            except Exception:
                logger.exception('Champion unavailable; keeping the previous model')
            stop.wait(interval)
    worker = threading.Thread(target=watch, daemon=True)
    worker.start()
    yield
    stop.set()
    worker.join(timeout=2)
    _db.dispose()


app = FastAPI(title='Property price API', lifespan=lifespan)


class Property(BaseModel):
    model_config = ConfigDict(json_schema_extra={'example': {
        'bed':3, 'bath':2, 'acre_lot':0.23, 'house_size':1837,
        'brokered_by':33714, 'street':1758218, 'city':'East Windsor',
        'state':'Connecticut', 'zip_code':6016}})
    bed: float | None = Field(default=None, ge=0)
    bath: float | None = Field(default=None, ge=0)
    acre_lot: float | None = Field(default=None, ge=0)
    house_size: float | None = Field(default=None, gt=0)
    brokered_by: float | str | None = None
    street: float | str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: float | str | None = None


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    try:
        body = await request.json()
        record(str(uuid.uuid4()), body, None, None, 'invalid', 'input validation failed')
    except Exception:
        logger.exception('Could not record invalid prediction request')
    return JSONResponse(status_code=422, content={'detail': exc.errors()})


@app.get('/health')
def health():
    return {'status':'ok', 'pod':POD_NAME}


@app.get('/ready')
def ready():
    with _state_lock:
        state = _state
    if state is None:
        raise HTTPException(503, 'No MLflow champion loaded')
    return {'status':'ready', 'model':MODEL_NAME, 'version':state['version'], 'pod':POD_NAME}


@app.post('/predict')
def predict(item: Property):
    request_id = str(uuid.uuid4())
    payload = item.model_dump()
    with _state_lock:
        state = _state
    if state is None:
        try:
            record(request_id, payload, None, None, 'unavailable', 'No champion loaded')
        except Exception:
            logger.exception('Could not record unavailable prediction')
        raise HTTPException(503, 'No MLflow champion loaded')
    try:
        prediction = float(state['model'].predict(pd.DataFrame([payload]))[0])
        record(request_id, payload, prediction, state['version'], 'success')
    except Exception as exc:
        logger.exception('Prediction failed')
        try:
            record(request_id, payload, None, state['version'], 'error', str(exc))
        except Exception:
            logger.exception('Could not record failed prediction')
        raise HTTPException(503, 'Prediction or audit storage failed') from exc
    return {'request_id':request_id, 'prediction':prediction, 'model':MODEL_NAME,
            'model_version':state['version'], 'pod':POD_NAME}
