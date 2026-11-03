# Keep these functions consistent with the modeling notebook.
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, confusion_matrix

def make_pipeline(frame,kind='logistic'):
    numbers=frame.select_dtypes(include='number').columns.tolist()
    categories=[c for c in frame.columns if c not in numbers]
    steps=[]
    if numbers: steps.append(('num',Pipeline([('fill',SimpleImputer(strategy='median',keep_empty_features=True)),('scale',StandardScaler())]),numbers))
    if categories: steps.append(('cat',Pipeline([('fill',SimpleImputer(strategy='constant',fill_value='missing',keep_empty_features=True)),('encode',OneHotEncoder(handle_unknown='ignore'))]),categories))
    prep=ColumnTransformer(steps)
    if kind not in ('logistic', 'forest'): raise ValueError(f'Unknown model: {kind}')
    model= LogisticRegression(max_iter=500,class_weight='balanced',random_state=42) if kind=='logistic' else RandomForestClassifier(n_estimators=100,min_samples_leaf=5,random_state=42,n_jobs=2,class_weight='balanced_subsample')
    return Pipeline([('preprocess',prep),('model',model)])

def score_predictions(y, predicted, probabilities):
    """Report counts and classification scores; undefined AUCs remain null."""
    y = np.asarray(y, dtype=int)
    predicted = np.asarray(predicted, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    if len(y) == 0:
        return None
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    result = {
        'n': int(len(y)), 'positive': int((y == 1).sum()), 'negative': int((y == 0).sum()),
        'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp),
        'accuracy': float(accuracy_score(y, predicted)),
        'precision': float(precision_score(y, predicted, zero_division=0)),
        'recall': float(recall_score(y, predicted, zero_division=0)),
        'f1': float(f1_score(y, predicted, zero_division=0)),
        'roc_auc': None, 'pr_auc': None,
    }
    if len(np.unique(y)) == 2:
        result['roc_auc'] = float(roc_auc_score(y, probabilities))
        # This is average precision, not trapezoidal PR-curve area.
        result['pr_auc'] = float(average_precision_score(y, probabilities))
    return result


def metrics(model, X, y):
    if len(y) == 0:
        return None
    positive_column = list(model.classes_).index(1)
    return score_predictions(y, model.predict(X), model.predict_proba(X)[:, positive_column])
