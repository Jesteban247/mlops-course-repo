import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

RAW_FEATURES = ['bed', 'bath', 'acre_lot', 'house_size', 'brokered_by', 'street', 'city', 'state', 'zip_code']
CATEGORICAL = ['brokered_by', 'street', 'city', 'state', 'zip_code']
NUMERIC = ['bed', 'bath', 'acre_lot', 'house_size', 'total_rooms', 'size_per_room']


def prepare(frame):
    result = frame.reindex(columns=RAW_FEATURES).copy()
    for col in ['bed', 'bath', 'acre_lot', 'house_size']:
        result[col] = pd.to_numeric(result[col], errors='coerce').replace([np.inf, -np.inf], np.nan).astype('float64')
    for col in CATEGORICAL:
        values = result[col].astype('string')
        if col in ('brokered_by', 'street', 'zip_code'):
            values = values.str.replace(r'(?<=\d)\.0+$', '', regex=True)
        result[col] = values.fillna('missing').astype(str)
    result['total_rooms'] = result['bed'] + result['bath']
    result['size_per_room'] = result['house_size'] / result['total_rooms'].where(result['total_rooms'] > 0)
    return result


def build_model():
    preprocess = ColumnTransformer([
        ('numeric', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), NUMERIC),
        ('categorical', OneHotEncoder(handle_unknown='infrequent_if_exist', min_frequency=20, max_categories=100), CATEGORICAL),
    ])
    return Pipeline([('features', FunctionTransformer(prepare, validate=False)), ('preprocess', preprocess), ('model', XGBRegressor(
        n_estimators=120, max_depth=5, learning_rate=.1, tree_method='hist', n_jobs=1, random_state=42))])
