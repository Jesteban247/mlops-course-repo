import csv
import json
import pickle

import pandas as pd
from airflow.providers.mysql.hooks.mysql import MySqlHook
from airflow.sdk import dag, task
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from utils.constants import CATEGORICAL, COLUMNS, CSV_PATH, MODEL_DIR, NUMERIC, PROCESSED_DIR

SPLIT_PATH = PROCESSED_DIR / "penguins_train_validation_test.pkl"


@dag(dag_id="penguins_pipeline", schedule=None, catchup=False, max_active_runs=1, tags=["penguins", "load", "preprocessing", "training"])
def penguins_pipeline():
    @task
    def load_csv_to_mysql():
        if not CSV_PATH.is_file():
            raise FileNotFoundError(f"Put the CSV at {CSV_PATH}")
        with CSV_PATH.open(newline="", encoding="utf-8") as file:
            rows = [tuple(None if row[col] in ("", "NA") else row[col] for col in COLUMNS) for row in csv.DictReader(file)]
        admin = MySqlHook(mysql_conn_id="mysql_admin")
        connection = admin.get_conn(); cursor = connection.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS palmerpenguins")
        cursor.execute("GRANT ALL PRIVILEGES ON palmerpenguins.* TO 'airflow_user'@'%'")
        cursor.execute("""CREATE TABLE IF NOT EXISTS palmerpenguins.penguins (species VARCHAR(50), island VARCHAR(50), bill_length_mm DECIMAL(5,2), bill_depth_mm DECIMAL(5,2), flipper_length_mm INT, body_mass_g INT, sex VARCHAR(20), year INT)""")
        connection.commit(); cursor.close(); connection.close()
        hook = MySqlHook(mysql_conn_id="palmerpenguins")
        hook.run("TRUNCATE TABLE penguins")
        hook.insert_rows("penguins", rows, target_fields=COLUMNS, commit_every=1000)
        print(f"Loaded {len(rows)} rows.")

    @task
    def preprocess():
        hook = MySqlHook(mysql_conn_id="palmerpenguins")
        rows = hook.get_records("SELECT species, island, bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g, sex FROM penguins")
        data = pd.DataFrame(rows, columns=COLUMNS).dropna().copy()
        data[NUMERIC] = data[NUMERIC].astype(float); data["flipper_length_mm"] = data["flipper_length_mm"].astype(int); data["body_mass_g"] = data["body_mass_g"].astype(int)
        hook.run("CREATE TABLE IF NOT EXISTS penguins_clean (species VARCHAR(50), island VARCHAR(50), bill_length_mm DECIMAL(5,2), bill_depth_mm DECIMAL(5,2), flipper_length_mm INT, body_mass_g INT, sex VARCHAR(20))")
        hook.run("TRUNCATE TABLE penguins_clean"); hook.insert_rows("penguins_clean", list(data.itertuples(index=False, name=None)), target_fields=COLUMNS)
        target = data.pop("species")
        x_train, x_rest, y_train, y_rest = train_test_split(data, target, test_size=.3, random_state=42, stratify=target)
        x_val, x_test, y_val, y_test = train_test_split(x_rest, y_rest, test_size=.5, random_state=42, stratify=y_rest)
        prep = ColumnTransformer([("numeric", StandardScaler(), NUMERIC), ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL)], verbose_feature_names_out=False)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        with SPLIT_PATH.open("wb") as file: pickle.dump({"X_train": prep.fit_transform(x_train), "y_train": y_train.to_numpy(), "X_validation": prep.transform(x_val), "y_validation": y_val.to_numpy(), "X_test": prep.transform(x_test), "y_test": y_test.to_numpy(), "preprocessor": prep, "feature_names": prep.get_feature_names_out().tolist()}, file)

    @task
    def train():
        with SPLIT_PATH.open("rb") as file: split = pickle.load(file)
        MODEL_DIR.mkdir(parents=True, exist_ok=True); metrics = {}
        for name, classifier in {"logistic_regression": LogisticRegression(max_iter=1000), "random_forest": RandomForestClassifier(n_estimators=300, random_state=42)}.items():
            classifier.fit(split["X_train"], split["y_train"]); predictions = classifier.predict(split["X_validation"])
            path = MODEL_DIR / f"penguins_{name}.pkl"
            with path.open("wb") as file: pickle.dump({"preprocessor": split["preprocessor"], "classifier": classifier, "feature_names": split["feature_names"], "model_name": name}, file)
            metrics[name] = {"validation_accuracy": float(accuracy_score(split["y_validation"], predictions)), "validation_macro_f1": float(f1_score(split["y_validation"], predictions, average="macro")), "model_file": path.name}
        (MODEL_DIR / "penguins_metrics.json").write_text(json.dumps(metrics, indent=2))

    load_csv_to_mysql() >> preprocess() >> train()


penguins_pipeline()
