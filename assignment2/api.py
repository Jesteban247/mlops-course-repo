from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from inference import available_models, predict


app = FastAPI(title="Iris Models API")


class PredictionRequest(BaseModel):
    model: str = Field(examples=["random_forest"])
    features: list[float] = Field(
        min_length=4,
        max_length=4,
        examples=[[5.1, 3.5, 1.4, 0.2]],
    )


class PredictionResponse(BaseModel):
    model: str
    prediction: int
    class_name: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/models")
def models():
    return {"models": available_models()}


@app.post("/predict", response_model=PredictionResponse)
def make_prediction(request: PredictionRequest):
    try:
        return predict(request.model, request.features)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
