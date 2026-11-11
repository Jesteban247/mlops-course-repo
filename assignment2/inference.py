from pathlib import Path
import json
import pickle


MODEL_DIR = Path("/app/models")
PRODUCTION_DIR = MODEL_DIR / "production"
MANIFEST_PATH = PRODUCTION_DIR / "manifest.json"
CLASS_NAMES = {0: "setosa", 1: "versicolor", 2: "virginica"}


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text())


def available_models() -> list[dict]:
    manifest = _load_manifest()
    return [{"name": name, **entry} for name, entry in sorted(manifest.items())]


def load_model(model_name: str):
    manifest = _load_manifest()
    if model_name not in manifest:
        names = ", ".join(sorted(manifest)) or "none"
        raise ValueError(f"Unknown model. Available models: {names}")

    version = manifest[model_name]["version"]
    model_path = PRODUCTION_DIR / model_name / version / "model.pkl"
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    with model_path.open("rb") as file:
        return pickle.load(file), version


def predict(model_name: str, features: list[float]) -> dict:
    if len(features) != 4:
        raise ValueError("Exactly 4 features are required")

    model, version = load_model(model_name)
    prediction = int(model.predict([features])[0])

    return {
        "model": model_name,
        "version": version,
        "prediction": prediction,
        "class_name": CLASS_NAMES[prediction],
    }
