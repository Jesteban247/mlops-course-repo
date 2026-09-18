import os
import pickle
from pathlib import Path

import pandas as pd

MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/app/models"))
SUPPORTED_MODELS = ("logistic_regression", "random_forest")


def available_models() -> list[str]:
    return [name for name in SUPPORTED_MODELS if (MODEL_DIR / f"penguins_{name}.pkl").is_file()]


def predict_penguin(features: dict, model_name: str) -> str:
    path = MODEL_DIR / f"penguins_{model_name}.pkl"
    if not path.is_file():
        raise FileNotFoundError(f"Model '{model_name}' is not available. Run penguins_pipeline first.")
    with path.open("rb") as file:
        bundle = pickle.load(file)
    return str(bundle["classifier"].predict(bundle["preprocessor"].transform(pd.DataFrame([features])))[0])
