import json
import math
from pathlib import Path

PAYLOAD = json.loads((Path(__file__).parent / "payload.json").read_text())


def validate_prediction(data):
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    rows = data.get("predictions")
    if not isinstance(rows, list) or len(rows) != len(PAYLOAD["instances"]):
        raise ValueError("Unexpected number of predictions")
    for row in rows:
        if not isinstance(row, dict) or row.get("prediction") not in {"No heart disease predicted", "Heart disease predicted"}:
            raise ValueError("Invalid prediction label")
        probabilities = row.get("probabilities_percent")
        if not isinstance(probabilities, dict):
            raise ValueError("Missing probabilities")
        values = [probabilities.get(name) for name in ("no_heart_disease", "heart_disease")]
        if not all(isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 100 for value in values):
            raise ValueError("Invalid probabilities")
        if abs(sum(values) - 100) > 0.02:
            raise ValueError("Probabilities must sum to 100 percent")
    if not data.get("model_uri") or not data.get("instance_id"):
        raise ValueError("Missing model or instance identity")
