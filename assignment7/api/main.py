"""A small FastAPI service for Assignment 7."""

import os
import random

from fastapi import FastAPI, Response
from pydantic import BaseModel

app = FastAPI(title="Assignment 7 API", version="1.0.0")


class Message(BaseModel):
    message: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/random")
def random_response(response: Response) -> dict[str, str | int]:
    response.headers["Connection"] = "close"
    return {
        "random_number": random.randint(1, 1_000_000),
        "pod": os.getenv("POD_NAME", "local"),
        "node": os.getenv("NODE_NAME", "local"),
    }


@app.post("/echo")
def echo(payload: Message) -> dict[str, str]:
    return {"message": payload.message}
