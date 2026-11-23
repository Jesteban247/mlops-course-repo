import numpy as np
from fastapi.testclient import TestClient

from api import main


class DummyModel:
    def predict(self, frame):
        assert 'house_size' in frame
        return np.array([230000.0])


def test_health_and_ready_without_model(monkeypatch):
    monkeypatch.setattr(main, '_state', None)
    client = TestClient(main.app)
    assert client.get('/health').status_code == 200
    assert client.get('/ready').status_code == 503


def test_prediction_returns_version_pod_and_audits(monkeypatch):
    records = []
    monkeypatch.setattr(main, '_state', {'model': DummyModel(), 'version': '3'})
    monkeypatch.setattr(main, 'record', lambda *args: records.append(args))
    client = TestClient(main.app)
    response = client.post('/predict', json={'bed':3, 'bath':2, 'house_size':1800, 'city':'Boston'})
    assert response.status_code == 200
    assert response.json()['prediction'] == 230000.0
    assert response.json()['model_version'] == '3'
    assert response.json()['pod']
    assert records[0][4] == 'success'


def test_invalid_input_is_rejected(monkeypatch):
    records = []
    monkeypatch.setattr(main, 'record', lambda *args: records.append(args))
    client = TestClient(main.app)
    assert client.post('/predict', json={'bed': -3}).status_code == 422
    assert records[0][4] == 'invalid'
