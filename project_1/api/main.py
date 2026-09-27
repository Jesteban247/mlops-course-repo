"""Prediction API serving the latest Covertype pipeline from MinIO."""

import io
from functools import lru_cache
import os
import time
from contextlib import asynccontextmanager

import boto3
import joblib
import pandas as pd
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

NUMERIC_FEATURES = [
    "elevation",
    "aspect",
    "slope",
    "horizontal_distance_to_hydrology",
    "vertical_distance_to_hydrology",
    "horizontal_distance_to_roadways",
    "hillshade_9am",
    "hillshade_noon",
    "hillshade_3pm",
    "horizontal_distance_to_fire_points",
]
CATEGORICAL_FEATURES = ["wilderness_area", "soil_type"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


@lru_cache(maxsize=1)
def minio_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT_URL", "http://minio:9000"),
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadmin12345"),
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def ensure_bucket():
    client = minio_client()
    bucket = os.getenv("MINIO_BUCKET", "covertype-models")
    for attempt in range(30):
        try:
            client.head_bucket(Bucket=bucket)
            return
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchBucket", "NotFound"}:
                try:
                    client.create_bucket(Bucket=bucket)
                    return
                except ClientError as create_error:
                    create_code = create_error.response.get("Error", {}).get("Code")
                    if create_code in {"BucketAlreadyExists", "BucketAlreadyOwnedByYou"}:
                        return
                    raise
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
            if status >= 500 and attempt < 29:
                time.sleep(2)
                continue
            raise
        except BotoCoreError:
            if attempt == 29:
                raise
            time.sleep(2)


def refresh_latest_model(app):
    client = minio_client()
    bucket = os.getenv("MINIO_BUCKET", "covertype-models")
    key = os.getenv("MINIO_MODEL_KEY", "models/covertype/latest/model.joblib")
    metadata = client.head_object(Bucket=bucket, Key=key)
    etag = metadata["ETag"]
    if etag != getattr(app.state, "model_etag", None):
        response = client.get_object(Bucket=bucket, Key=key)
        app.state.model = joblib.load(io.BytesIO(response["Body"].read()))
        app.state.model_etag = etag
    return app.state.model


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bucket()
    app.state.model = None
    app.state.model_etag = None
    try:
        refresh_latest_model(app)
    except ClientError:
        pass
    yield


app = FastAPI(title="Covertype Prediction API", version="1.0.0", lifespan=lifespan)


class PredictionRequest(BaseModel):
    features: dict[str, str | int | float] = Field(
        examples=[
            {
                "elevation": 2596,
                "aspect": 51,
                "slope": 3,
                "horizontal_distance_to_hydrology": 258,
                "vertical_distance_to_hydrology": 0,
                "horizontal_distance_to_roadways": 510,
                "hillshade_9am": 221,
                "hillshade_noon": 232,
                "hillshade_3pm": 148,
                "horizontal_distance_to_fire_points": 6279,
                "wilderness_area": "1",
                "soil_type": "29",
            }
        ]
    )


@app.get("/health")
def health():
    try:
        refresh_latest_model(app)
    except ClientError:
        pass
    return {"status": "ok", "model_loaded": app.state.model is not None}


@app.post("/predict")
def predict(request: PredictionRequest):
    missing = sorted(set(FEATURES) - request.features.keys())
    extra = sorted(request.features.keys() - set(FEATURES))
    if missing or extra:
        raise HTTPException(
            status_code=422,
            detail={"missing_features": missing, "unexpected_features": extra},
        )
    try:
        model = refresh_latest_model(app)
    except ClientError as error:
        raise HTTPException(
            status_code=503,
            detail="No latest model is available. Run 02_train.ipynb and upload the model to MinIO.",
        ) from error

    row = {name: request.features[name] for name in FEATURES}
    for name in NUMERIC_FEATURES:
        try:
            row[name] = float(row[name])
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=f"{name} must be numeric") from error
    frame = pd.DataFrame([row], columns=FEATURES)
    for name in CATEGORICAL_FEATURES:
        frame[name] = frame[name].astype(str)
    prediction = int(model.predict(frame)[0])
    return {"predicted_cover_type": prediction}
