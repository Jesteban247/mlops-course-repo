"""Small text-preprocessing API for the MLOps assignment."""

import re
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="ML Preprocessing API", version="1.0.0")


def normalize_text(text: str) -> str:
    """Lowercase text, remove punctuation, and collapse repeated whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def tokenize_text(text: str) -> List[str]:
    """Split normalized text into word tokens."""
    return normalize_text(text).split()


def remove_stopwords(tokens: List[str], stopwords: List[str]) -> List[str]:
    """Remove any tokens present in the supplied stopword list."""
    ignored = {word.lower() for word in stopwords}
    return [token for token in tokens if token.lower() not in ignored]


class PreprocessRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": "This is a SIMPLE example!",
                    "stopwords": ["a", "an", "the", "is"],
                }
            ]
        }
    )

    text: str = Field(..., min_length=1)
    stopwords: List[str] = Field(default_factory=lambda: ["a", "an", "the", "is"])


@app.get("/health")
def health():
    """Container and API health check."""
    return {"status": "ok"}


@app.post("/preprocess")
def preprocess(request: PreprocessRequest):
    normalized = normalize_text(request.text)
    tokens = tokenize_text(request.text)
    filtered_tokens = remove_stopwords(tokens, request.stopwords)
    return {
        "original_text": request.text,
        "normalized_text": normalized,
        "tokens": tokens,
        "filtered_tokens": filtered_tokens,
    }

