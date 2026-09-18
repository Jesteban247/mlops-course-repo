from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from inference import available_models, predict_penguin

app = FastAPI(title="Palmer Penguins API")
state = {"active_model": "random_forest"}


class PenguinFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"island": "Torgersen", "bill_length_mm": 39.1, "bill_depth_mm": 18.7, "flipper_length_mm": 181, "body_mass_g": 3750, "sex": "MALE"}]})
    island: str = Field(examples=["Torgersen"])
    bill_length_mm: float = Field(examples=[39.1])
    bill_depth_mm: float = Field(examples=[18.7])
    flipper_length_mm: int = Field(examples=[181])
    body_mass_g: int = Field(examples=[3750])
    sex: Literal["MALE", "FEMALE"] = Field(examples=["MALE"])


class ModelSelection(BaseModel):
    model_name: str = Field(examples=["random_forest"])


@app.get("/health")
def health():
    return {"status": "ok", "active_model": state["active_model"], "models_available": available_models()}


@app.get("/models")
def models():
    return {"available_models": available_models(), "active_model": state["active_model"]}


@app.post("/models/select")
def select_model(selection: ModelSelection):
    if selection.model_name not in available_models():
        raise HTTPException(404, f"Model not found. Available models: {available_models()}")
    state["active_model"] = selection.model_name
    return {"active_model": selection.model_name}


@app.post("/predict")
def predict(features: PenguinFeatures):
    try:
        return {"model": state["active_model"], "predicted_species": predict_penguin(features.model_dump(), state["active_model"])}
    except FileNotFoundError as error:
        raise HTTPException(503, str(error)) from error
