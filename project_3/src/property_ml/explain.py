"""Explain fitted XGBoost predictions on held-out properties."""
import pandas as pd
from xgboost import DMatrix


def shap_importance(model, validation):
    sample = validation.sample(n=min(len(validation), 500), random_state=42)
    transformed = model[:-1].transform(sample)
    booster = model.named_steps['model'].get_booster()
    values = booster.predict(DMatrix(transformed), pred_contribs=True)
    names = model.named_steps['preprocess'].get_feature_names_out()
    contributions = pd.DataFrame(values[:, :-1], columns=names, index=sample.index)
    return contributions.abs().mean().sort_values(ascending=False)
