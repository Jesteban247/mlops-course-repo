"""Make one penguin species prediction with the trained model."""

import argparse
import pickle
import pandas as pd

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "penguin_tree.pkl"


def predict_penguin(island, bill_length, bill_depth, flipper_length, body_mass, sex):
    """Return the predicted species for one penguin."""
    with MODEL_PATH.open("rb") as file:
        model = pickle.load(file)

    penguin = pd.DataFrame([{
        "island": island,
        "bill_length_mm": bill_length,
        "bill_depth_mm": bill_depth,
        "flipper_length_mm": flipper_length,
        "body_mass_g": body_mass,
        "sex": sex,
    }])
    return model.predict(penguin)[0]


def main():
    parser = argparse.ArgumentParser(description="Predict a penguin species")
    parser.add_argument("--island", default="Dream")
    parser.add_argument("--bill-length", type=float, default=45.0)
    parser.add_argument("--bill-depth", type=float, default=15.0)
    parser.add_argument("--flipper-length", type=float, default=210.0)
    parser.add_argument("--body-mass", type=float, default=4500.0)
    parser.add_argument("--sex", default="MALE", choices=["MALE", "FEMALE"])
    args = parser.parse_args()

    prediction = predict_penguin(
        args.island,
        args.bill_length,
        args.bill_depth,
        args.flipper_length,
        args.body_mass,
        args.sex,
    )
    print(f"Predicted species: {prediction}")


if __name__ == "__main__":
    main()
