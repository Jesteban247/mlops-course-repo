import numpy as np
import pandas as pd

from property_ml.decisions import decide, psi, promotion_decision
from property_ml.features import RAW_FEATURES, build_model, prepare
from property_ml.splitting import split_for_property as _split


def test_retraining_requires_change_and_accumulates_small_batches():
    assert decide(0, 100, 1, {}, {}) == ('train', 'initial baseline')
    assert decide(1000, 20, 1, {'bed': 1.0}, {})[0] == 'skip'
    assert decide(1000, 100, 1, {'bed': .01}, {})[0] == 'skip'
    assert decide(1000, 100, 1, {'bed': .30}, {})[0] == 'train'
    assert decide(1000, 100, .5, {'bed': .30}, {})[0] == 'skip'


def test_psi_detects_numerical_distribution_change():
    baseline = pd.Series(np.arange(1000))
    assert psi(baseline, baseline) < .001
    assert psi(baseline, baseline + 500) > .2


def test_stable_property_split_ignores_price_changes():
    a = {'street': 10, 'city': 'Boston', 'state': 'MA', 'price': 100}
    b = dict(a, street=10.0, city='boston ', price=150)
    assert _split(a, 1) == _split(b, 2)
    assert _split(dict(a, street=None), 1) != _split(dict(a, street=None), 2)


def test_selected_model_predicts_unknown_categories():
    rows = []
    for i in range(50):
        rows.append({'bed': 2+i%4, 'bath': 1+i%3, 'acre_lot': .2, 'house_size': 1200+i*10,
                     'brokered_by': i%3, 'street': i, 'city': 'A', 'state': 'PA', 'zip_code': 12345})
    frame = pd.DataFrame(rows, columns=RAW_FEATURES)
    model = build_model()
    model.fit(frame, np.arange(50)*1000 + 100000)
    new = frame.iloc[:1].copy()
    new.loc[:, 'city'] = 'new-city'
    assert np.isfinite(model.predict(new)[0])


def test_mlflow_model_roundtrip(tmp_path):
    import mlflow.sklearn
    frame = pd.DataFrame([{'bed': 3, 'bath': 2, 'acre_lot': .2, 'house_size': 1200+i,
                           'brokered_by': i % 3, 'street': i, 'city': 'A', 'state': 'PA', 'zip_code': 12345}
                          for i in range(30)])
    features = frame
    model = build_model().fit(features, np.arange(30)*500 + 100000)
    target = tmp_path / 'model'
    mlflow.sklearn.save_model(model, str(target), serialization_format='cloudpickle', pip_requirements=[])
    restored = mlflow.sklearn.load_model(str(target))
    np.testing.assert_allclose(model.predict(features.iloc[:3]), restored.predict(features.iloc[:3]))


def test_promotion_requires_better_finite_mae():
    import pytest
    assert promotion_decision(10, None)[0]
    assert promotion_decision(9, 10)[0]
    assert not promotion_decision(10, 10)[0]
    assert not promotion_decision(11, 10)[0]
    with pytest.raises(ValueError):
        promotion_decision(float('nan'), None)


def test_data_validation_flags_impossible_values_and_keeps_outliers():
    from property_ml.validation import validate, possible_extreme
    row = {'price': 150000, 'bed': 3, 'bath': 2, 'acre_lot': .2, 'house_size': 1800,
           'brokered_by': 1, 'street': 4, 'city': 'A', 'state': 'PA', 'zip_code': 123,
           'status': 'for_sale', 'prev_sold_date': None}
    assert validate(row) == (True, 'valid')
    assert validate(dict(row, price=0))[0] is False
    assert validate(dict(row, bed=-1))[0] is False
    assert validate(dict(row, city=['A']))[0] is False
    assert validate(dict(row, bed=190))[0] is True
    assert possible_extreme(dict(row, bed=190))


def test_encoded_numeric_identifiers_match_across_json_and_api_types():
    integer = pd.DataFrame([{'street': 123, 'zip_code': 6016, 'brokered_by': 5}])
    decimal = pd.DataFrame([{'street': '123.0', 'zip_code': 6016.0, 'brokered_by': '5.0'}])
    one, two = prepare(integer), prepare(decimal)
    for column in ['street', 'zip_code', 'brokered_by']:
        assert one[column].iloc[0] == two[column].iloc[0]


def test_candidate_without_champion_is_baseline(monkeypatch):
    from types import SimpleNamespace
    from property_ml import training

    class DummyModel:
        def predict(self, frame):
            return np.array([100.0, 200.0])

    db = SimpleNamespace(dispose=lambda: None)
    frame = pd.DataFrame([{'split': 'validation', 'price': 100.0},
                          {'split': 'validation', 'price': 200.0}])
    client = SimpleNamespace(get_registered_model=lambda name: SimpleNamespace(aliases={}))
    monkeypatch.setenv('MLFLOW_TRACKING_URI', 'http://unused')
    monkeypatch.setattr(training, 'engine', lambda: db)
    monkeypatch.setattr(training, '_frame', lambda *args, **kwargs: frame)
    monkeypatch.setattr(training, 'MlflowClient', lambda: client)
    monkeypatch.setattr(training.mlflow, 'set_tracking_uri', lambda uri: None)
    monkeypatch.setattr(training.mlflow.sklearn, 'load_model', lambda uri: DummyModel())
    result = training.compare_candidate({'batch': 0, 'model_version': '1', 'run_id': 'run'})
    assert result['promoted'] is True
    assert result['reason'] == 'initial model'
