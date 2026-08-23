"""Train Decision Tree and XGBoost classifiers for the penguins dataset."""

import pickle
import pandas as pd

from pathlib import Path
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier


DATA_PATH = Path("data/penguins_clean.csv")
MODELS_DIR = Path("models")


class XGBoostWrapper:
    """Wraps XGBoost pipeline + LabelEncoder con la misma interfaz que un Pipeline de sklearn."""

    def __init__(self, pipeline, label_encoder):
        self.pipeline = pipeline
        self.label_encoder = label_encoder

    def predict(self, X):
        numeric_preds = self.pipeline.predict(X)
        return self.label_encoder.inverse_transform(numeric_preds)


def build_preprocessing():
    """Preprocesamiento compartido para ambos modelos."""
    categorical_features = ["island", "sex"]
    numeric_features = [
        "bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g",
    ]
    return ColumnTransformer(
        transformers=[
            ("numeric", SimpleImputer(strategy="median"), numeric_features),
            (
                "categorical",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("encoder", OneHotEncoder(handle_unknown="ignore")),
                ]),
                categorical_features,
            ),
        ]
    )


def train_decision_tree(X_train, X_test, y_train, y_test):
    print("\n=== Decision Tree + GridSearchCV ===")
    pipeline = Pipeline([
        ("preprocessing", build_preprocessing()),
        ("classifier", DecisionTreeClassifier(random_state=42)),
    ])
    param_grid = {
        "classifier__max_depth": [3, 4, 5, 6, None],
        "classifier__min_samples_split": [2, 5, 10],
        "classifier__min_samples_leaf": [1, 2, 4],
    }
    grid = GridSearchCV(pipeline, param_grid, cv=5, scoring="accuracy", n_jobs=-1)
    grid.fit(X_train, y_train)

    best = grid.best_estimator_
    preds = best.predict(X_test)
    print(f"Best params  : {grid.best_params_}")
    print(f"CV accuracy  : {grid.best_score_:.4f}")
    print(f"Test accuracy: {accuracy_score(y_test, preds):.4f}")
    print(classification_report(y_test, preds))
    return best


def train_xgboost(X_train, X_test, y_train, y_test):
    print("\n=== XGBoost + GridSearchCV ===")

    # XGBoost requiere labels numéricas
    le = LabelEncoder()
    y_train_enc = le.fit_transform(y_train)
    y_test_enc = le.transform(y_test)

    pipeline = Pipeline([
        ("preprocessing", build_preprocessing()),
        ("classifier", XGBClassifier(random_state=42, n_jobs=-1)),
    ])
    param_grid = {
        "classifier__n_estimators": [100, 200],
        "classifier__max_depth": [3, 4, 5],
        "classifier__learning_rate": [0.05, 0.1, 0.2],
        "classifier__subsample": [0.8, 1.0],
    }
    grid = GridSearchCV(pipeline, param_grid, cv=5, scoring="accuracy", n_jobs=-1)
    grid.fit(X_train, y_train_enc)

    best_pipeline = grid.best_estimator_
    preds_enc = best_pipeline.predict(X_test)
    preds = le.inverse_transform(preds_enc)

    print(f"Best params  : {grid.best_params_}")
    print(f"CV accuracy  : {grid.best_score_:.4f}")
    print(f"Test accuracy: {accuracy_score(y_test, preds):.4f}")
    print(classification_report(y_test, preds))

    return XGBoostWrapper(best_pipeline, le)


def main():
    data = pd.read_csv(DATA_PATH)
    features = [
        "island", "bill_length_mm", "bill_depth_mm",
        "flipper_length_mm", "body_mass_g", "sex",
    ]
    X = data[features]
    y = data["species"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    MODELS_DIR.mkdir(exist_ok=True)

    tree = train_decision_tree(X_train, X_test, y_train, y_test)
    with (MODELS_DIR / "penguin_tree.pkl").open("wb") as f:
        pickle.dump(tree, f)
    print("\nSaved → models/penguin_tree.pkl")

    xgb = train_xgboost(X_train, X_test, y_train, y_test)
    with (MODELS_DIR / "penguin_xgboost.pkl").open("wb") as f:
        pickle.dump(xgb, f)
    print("Saved → models/penguin_xgboost.pkl")


if __name__ == "__main__":
    main()