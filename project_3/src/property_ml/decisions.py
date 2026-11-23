"""Explicit, provisional data-driven retraining rules."""
import numpy as np
import pandas as pd


def psi(reference, current, discrete=False):
    ref = pd.to_numeric(reference, errors='coerce').dropna().to_numpy()
    cur = pd.to_numeric(current, errors='coerce').dropna().to_numpy()
    ref, cur = ref[np.isfinite(ref)], cur[np.isfinite(cur)]
    if len(ref) < 2 or len(cur) < 2:
        return np.nan
    if discrete:
        values = np.union1d(ref, cur)
        r = pd.Series(ref).value_counts(normalize=True).reindex(values, fill_value=0).to_numpy()
        c = pd.Series(cur).value_counts(normalize=True).reindex(values, fill_value=0).to_numpy()
    else:
        edges = np.unique(np.quantile(ref, np.linspace(0, 1, 11)))
        if len(edges) < 2:
            return np.nan
        edges[0], edges[-1] = -np.inf, np.inf
        r = np.histogram(ref, bins=edges)[0] / len(ref)
        c = np.histogram(cur, bins=edges)[0] / len(cur)
    r, c = np.maximum(r, 1e-6), np.maximum(c, 1e-6)
    return float(((c - r) * np.log(c / r)).sum())


def decide(trained_count, pending_count, valid_fraction, drift, category_fraction,
           min_contribution=.05, min_valid=.80, min_category=.05, min_psi=.20, new_fraction=1.0, min_new=.10):
    if pending_count < 3 or valid_fraction < min_valid:
        return 'skip', 'insufficient valid data'
    if new_fraction < min_new:
        return 'skip', 'new row percentage below threshold'
    if trained_count == 0:
        return 'train', 'initial baseline'
    if pending_count / trained_count < min_contribution:
        return 'skip', 'new data below contribution threshold'
    signals = [f'{name} distribution' for name, value in drift.items()
               if np.isfinite(value) and value >= min_psi]
    signals += [f'new {name}' for name, value in category_fraction.items() if value >= min_category]
    if not drift:
        return 'skip', 'distribution unavailable'
    return ('train', ', '.join(signals)) if signals else ('skip', 'no change threshold met')


def promotion_decision(candidate_mae, champion_mae):
    if not np.isfinite(candidate_mae):
        raise ValueError('Candidate MAE must be finite')
    if champion_mae is None:
        return True, 'initial model'
    if not np.isfinite(champion_mae):
        raise ValueError('Champion MAE must be finite')
    if candidate_mae < champion_mae:
        return True, 'lower validation MAE'
    return False, 'validation MAE did not improve'
