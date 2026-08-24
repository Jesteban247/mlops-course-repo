"""Small FastAPI service for penguin species predictions."""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from inference import predict_penguin

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"

app = FastAPI(title="Penguin Species API")

# Keep the active model in one place so it can be changed through the API.
_state = {"active_model": "penguin_tree"}


class Penguin(BaseModel):
    island: str = "Dream"
    bill_length: float = 45.0
    bill_depth: float = 15.0
    flipper_length: float = 210.0
    body_mass: float = 4500.0
    sex: Literal["MALE", "FEMALE"] = "MALE"


class ModelSelection(BaseModel):
    model_name: str


@app.get("/")
def home():
    return {"message": "Penguin species API is running"}


@app.get("/models")
def list_models():
    """List available trained models and identify the active model."""
    available = sorted(p.stem for p in MODELS_DIR.glob("*.pkl"))
    return {
        "available_models": available,
        "active_model": _state["active_model"],
    }


@app.post("/models/select")
def select_model(selection: ModelSelection):
    """Select the model used for future predictions."""
    model_path = MODELS_DIR / f"{selection.model_name}.pkl"
    if not model_path.exists():
        available = sorted(p.stem for p in MODELS_DIR.glob("*.pkl"))
        raise HTTPException(
            status_code=404,
            detail=f"Model '{selection.model_name}' not found. Available: {available}",
        )
    _state["active_model"] = selection.model_name
    return {"message": f"Active model set to '{selection.model_name}'"}


@app.post("/predict")
def predict(penguin: Penguin):
    """Predict a penguin species with the active model."""
    try:
        species = predict_penguin(
            penguin.island,
            penguin.bill_length,
            penguin.bill_depth,
            penguin.flipper_length,
            penguin.body_mass,
            penguin.sex,
            model_name=_state["active_model"],
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Model not found. Run 'python train.py' first.",
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {error}",
        )

    return {
        "predicted_species": species,
        "model_used": _state["active_model"],
    }
