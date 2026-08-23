"""Small FastAPI service for penguin species predictions."""

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from inference import predict_penguin


app = FastAPI(title="Penguin Species API")


class Penguin(BaseModel):
    island: str = "Dream"
    bill_length: float = 45.0
    bill_depth: float = 15.0
    flipper_length: float = 210.0
    body_mass: float = 4500.0
    sex: Literal["MALE", "FEMALE"] = "MALE"


@app.get("/")
def home():
    return {"message": "Penguin species API is running"}


@app.post("/predict")
def predict(penguin: Penguin):
    try:
        species = predict_penguin(
            penguin.island,
            penguin.bill_length,
            penguin.bill_depth,
            penguin.flipper_length,
            penguin.body_mass,
            penguin.sex,
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

    return {"predicted_species": species}
