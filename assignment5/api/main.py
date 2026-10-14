import logging
import math
import os
import socket
from contextlib import asynccontextmanager
from threading import Lock
from typing import Literal

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

MODEL_URI = os.environ["MLFLOW_MODEL_URI"]
INSTANCE_ID = socket.gethostname()
logger = logging.getLogger("uvicorn.error")
model_lock = Lock()
FEATURES = ["age", "sex", "cp", "trestbps", "chol", "fbs", "restecg", "thalach", "exang", "oldpeak", "slope", "ca", "thal"]
EXAMPLE = dict(zip(FEATURES, [63, 1, 1, 145, 233, 1, 2, 150, 0, 2.3, 3, 0, 6]))


@asynccontextmanager
async def lifespan(app: FastAPI):
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    app.state.model = None
    if os.getenv("PRELOAD_MODEL", "true").lower() == "true":
        get_model()
    yield
    app.state.model = None


app = FastAPI(title="Heart Disease Inference API", version="1.0.0", lifespan=lifespan)


def get_model():
    if app.state.model is None:
        with model_lock:
            if app.state.model is None:
                try:
                    logger.info("Loading %s for instance %s", MODEL_URI, INSTANCE_ID)
                    app.state.model = mlflow.sklearn.load_model(MODEL_URI)
                except Exception as exc:
                    logger.exception("Model unavailable")
                    raise HTTPException(503, "Model unavailable; run train_model.ipynb first") from exc
    return app.state.model


class PredictionRequest(BaseModel):
    instances: list[dict[str, float]] = Field(min_length=1)
    model_config = {"json_schema_extra": {"examples": [{"instances": [EXAMPLE]}]}}


class Probabilities(BaseModel):
    no_heart_disease: float = Field(ge=0, le=100)
    heart_disease: float = Field(ge=0, le=100)


class Prediction(BaseModel):
    prediction: Literal["No heart disease predicted", "Heart disease predicted"]
    probabilities_percent: Probabilities


class PredictionResponse(BaseModel):
    predictions: list[Prediction]
    model_uri: str
    instance_id: str


@app.get("/health")
def health(response: Response):
    get_model()
    response.headers["X-API-Instance"] = INSTANCE_ID
    return {"status": "ok", "model_uri": MODEL_URI, "instance_id": INSTANCE_ID}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest, response: Response):
    response.headers["X-API-Instance"] = INSTANCE_ID
    model = get_model()
    expected = list(model.feature_names_in_)
    for index, row in enumerate(request.instances):
        missing = sorted(set(expected) - row.keys())
        extra = sorted(row.keys() - set(expected))
        if missing or extra:
            raise HTTPException(422, {"row": index, "missing_features": missing, "unexpected_features": extra})
    frame = pd.DataFrame(request.instances, columns=expected)
    if not all(math.isfinite(value) for row in request.instances for value in row.values()):
        raise HTTPException(422, "Features must be finite numbers")
    try:
        classes = [int(value) for value in model.classes_]
        if set(classes) != {0, 1}:
            raise ValueError("Expected binary classes 0 and 1")
        labels = {0: "No heart disease predicted", 1: "Heart disease predicted"}
        predictions = []
        for prediction, probabilities in zip(model.predict(frame), model.predict_proba(frame)):
            by_class = dict(zip(classes, probabilities))
            predictions.append({
                "prediction": labels[int(prediction)],
                "probabilities_percent": {
                    "no_heart_disease": round(float(by_class[0]) * 100, 2),
                    "heart_disease": round(float(by_class[1]) * 100, 2),
                },
            })
        return {"predictions": predictions, "model_uri": MODEL_URI, "instance_id": INSTANCE_ID}
    except Exception as exc:
        logger.exception("Inference failed")
        raise HTTPException(503, "Inference failed") from exc
