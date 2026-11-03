# Keep these functions consistent with the preprocessing notebook.
import hashlib
import numpy as np
import pandas as pd
NUMERIC_FEATURES = (
    'time_in_hospital', 'num_lab_procedures', 'num_procedures',
    'num_medications', 'number_outpatient', 'number_emergency',
    'number_inpatient', 'number_diagnoses',
)
SPLIT_STRATEGY = 'patient_nbr_sha256_70_15_15'

def split_for_patient(patient_id):
    value = int(hashlib.sha256(str(int(patient_id)).encode()).hexdigest()[:12], 16) % 10000
    return 'train' if value < 7000 else ('validation' if value < 8500 else 'test')

def normalize_features(features):
    """Keep categorical columns categorical, even when an entire batch is missing."""
    result = features.copy()
    result = result.mask(result.eq('?'))
    for column in result:
        if column in NUMERIC_FEATURES:
            result[column] = pd.to_numeric(result[column], errors='coerce').astype('float64')
        else:
            result[column] = result[column].map(
                lambda value: str(value) if pd.notna(value) else np.nan
            ).astype(object)
    return result

def prepare_records(df):
    required = {'encounter_id', 'patient_nbr', 'readmitted'}
    if not required.issubset(df.columns):
        raise ValueError(f'Missing columns: {required - set(df.columns)}')
    df = df.copy().reset_index(drop=True)
    df = df.mask(df.eq('?'))
    if df[['encounter_id', 'patient_nbr', 'readmitted']].isna().any().any():
        raise ValueError('Encounter ID, patient ID and readmission label are required')
    unexpected = set(df['readmitted'].unique()) - {'NO', '>30', '<30'}
    if unexpected:
        raise ValueError(f'Unexpected readmission labels: {unexpected}')
    df['target'] = df['readmitted'].eq('<30').astype('int8')
    df['split'] = df['patient_nbr'].map(split_for_patient)
    excluded = {'encounter_id', 'patient_nbr', 'readmitted', 'target', 'split', 'discharge_disposition_id'}
    features = normalize_features(df.drop(columns=[c for c in excluded if c in df.columns]))
    return df[['encounter_id', 'patient_nbr', 'target', 'split']], features
