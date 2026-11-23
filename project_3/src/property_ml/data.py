"""Load accumulated clean records for decisions and training."""
import pandas as pd
from sqlalchemy import text

from property_ml.features import RAW_FEATURES
from property_ml.settings import GROUP


def _frame(db, after=None, through=None):
    fields = ', '.join(f"features->>'{name}' AS {name}" for name in RAW_FEATURES + ['status'])
    query = f'''SELECT batch_number,split,price,{fields} FROM clean.properties
               WHERE group_number=:g AND (:after IS NULL OR batch_number>:after)
               AND (:through IS NULL OR batch_number<=:through) ORDER BY raw_id'''
    with db.connect() as conn:
        return pd.read_sql_query(text(query), conn, params={'g': GROUP, 'after': after, 'through': through})
