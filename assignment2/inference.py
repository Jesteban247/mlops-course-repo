from pathlib import Path
import pickle


MODEL_DIR = Path("/app/models")
CLASS_NAMES = {0: "setosa", 1: "versicolor", 2: "virginica"}


def available_models() -> list[str]:
    return sorted(path.stem for path in MODEL_DIR.glob("*.pkl"))


def load_model(model_name: str):
    if model_name not in available_models():
        models = ", ".join(available_models()) or "none"
        raise ValueError(f"Unknown model. Available models: {models}")

    model_path = MODEL_DIR / f"{model_name}.pkl"
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    with model_path.open("rb") as file:
        return pickle.load(file)


def predict(model_name: str, features: list[float]) -> dict:
    if len(features) != 4:
        raise ValueError("Exactly 4 features are required")

    model = load_model(model_name)
    prediction = int(model.predict([features])[0])

    return {
        "model": model_name,
        "prediction": prediction,
        "class_name": CLASS_NAMES[prediction],
    }
