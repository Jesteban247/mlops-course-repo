import os
from typing import Any, Literal

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODEL_URI = os.getenv(
    "MLFLOW_MODEL_URI", "models:/HeartDiseaseClassifier@champion"
)
mlflow.set_tracking_uri(TRACKING_URI)

app = FastAPI(title="Heart Disease Inference API", version="1.0.0")
_model: Any = None


class PredictionRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "instances": [
                        {
                            "age": 63,
                            "sex": 1,
                            "cp": 1,
                            "trestbps": 145,
                            "chol": 233,
                            "fbs": 1,
                            "restecg": 2,
                            "thalach": 150,
                            "exang": 0,
                            "oldpeak": 2.3,
                            "slope": 3,
                            "ca": 0,
                            "thal": 6,
                        }
                    ]
                }
            ]
        }
    )
    instances: list[dict[str, float]] = Field(
        ..., min_length=1, description="Rows keyed by the UCI feature names"
    )


class DiseaseProbabilities(BaseModel):
    no_heart_disease: float = Field(..., ge=0, le=100)
    heart_disease: float = Field(..., ge=0, le=100)


class PredictionResult(BaseModel):
    prediction: Literal["No heart disease predicted", "Heart disease predicted"]
    probabilities_percent: DiseaseProbabilities = Field(
        ..., description="Model probabilities expressed as percentages"
    )


class PredictionResponse(BaseModel):
    predictions: list[PredictionResult]


def load_model() -> Any:
    global _model
    if _model is None:
        _model = mlflow.sklearn.load_model(MODEL_URI)
    return _model


@app.get("/health")
def health() -> dict[str, str]:
    try:
        load_model()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Model unavailable from MLflow ({MODEL_URI}): {exc}",
        ) from exc
    return {"status": "ok", "model_uri": MODEL_URI}


@app.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Predict heart disease",
    description="Returns one model prediction per input row with labeled probabilities in percent.",
)
def predict(request: PredictionRequest) -> dict[str, Any]:
    try:
        model = load_model()
        frame = pd.DataFrame(request.instances)
        expected = list(model.feature_names_in_)
        missing = [name for name in expected if name not in frame.columns]
        extra = [name for name in frame.columns if name not in expected]
        if missing or extra:
            raise HTTPException(
                status_code=422,
                detail={"missing_features": missing, "unexpected_features": extra},
            )
        frame = frame[expected]
        classes = [int(value) for value in model.classes_]
        if set(classes) != {0, 1}:
            raise ValueError("Expected model classes 0 (no disease) and 1 (disease)")
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
        return {"predictions": predictions}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not load or run the registered MLflow model: {exc}",
        ) from exc
