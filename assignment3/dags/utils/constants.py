from pathlib import Path

CSV_PATH = Path("/opt/airflow/data/penguins.csv")
PROCESSED_DIR = Path("/opt/airflow/data/processed")
MODEL_DIR = Path("/opt/airflow/models")
COLUMNS = ["species", "island", "bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g", "sex"]
NUMERIC = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g"]
CATEGORICAL = ["island", "sex"]
