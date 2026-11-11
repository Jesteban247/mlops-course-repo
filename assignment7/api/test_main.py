from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_echo():
    response = client.post("/echo", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json() == {"message": "hello"}


def test_random(monkeypatch):
    monkeypatch.setenv("POD_NAME", "api-pod")
    monkeypatch.setenv("NODE_NAME", "worker-node")
    response = client.get("/random")
    assert response.status_code == 200
    body = response.json()
    assert 1 <= body["random_number"] <= 1_000_000
    assert body["pod"] == "api-pod"
    assert body["node"] == "worker-node"
    assert response.headers["connection"] == "close"


def test_root_is_not_a_second_random_endpoint():
    assert client.get("/").status_code == 404
