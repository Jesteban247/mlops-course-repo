from fastapi.testclient import TestClient

from app import app, normalize_text, remove_stopwords, tokenize_text

client = TestClient(app)


def test_normalize_text():
    assert normalize_text("  Hello,   WORLD! ") == "hello"


def test_tokenize_text():
    assert tokenize_text("FastAPI makes ML easy.") == ["fastapi", "makes", "ml", "easy"]


def test_remove_stopwords():
    assert remove_stopwords(["this", "is", "useful"], ["is"]) == ["this", "useful"]


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_preprocess_endpoint():
    response = client.post("/preprocess", json={"text": "This is a SIMPLE example!"})
    assert response.status_code == 200
    assert response.json()["normalized_text"] == "this is a simple example"
    assert response.json()["filtered_tokens"] == ["this", "simple", "example"]


def test_preprocess_rejects_empty_text():
    response = client.post("/preprocess", json={"text": ""})
    assert response.status_code == 422


