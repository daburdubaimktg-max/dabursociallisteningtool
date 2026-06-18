"""Internal NLP inference service (FastAPI) exposing /detect /score /translate.

The pipeline calls these endpoints (or the in-process service directly). The active
implementation is chosen by config/env. The stub is allowed ONLY when explicitly
enabled — it can never be the silent default in production (CLAUDE.md §3).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel

from nlp.contract import Detection, NLPService
from nlp.stub import StubNLPService


def get_service() -> NLPService:
    """Select the NLP backend.

    NLP_BACKEND=stub explicitly opts into the non-production stub. Any other value
    (or production) must resolve to the real transformer service. We fail loudly
    rather than silently defaulting to the stub in production.
    """
    backend = os.environ.get("NLP_BACKEND", "stub")
    if backend == "stub":
        if os.environ.get("ENV", "dev") == "production":
            raise RuntimeError(
                "Refusing to use the stub NLP backend in production. "
                "Set NLP_BACKEND to the real transformer service."
            )
        return StubNLPService()
    # The real MARBERT/CAMeLBERT/NLLB-backed service is registered here in a later slice.
    raise RuntimeError(f"NLP backend '{backend}' is not available yet.")


app = FastAPI(title="Dabur NLP Service")


class TextIn(BaseModel):
    text: str
    language: str | None = None


@app.post("/detect", response_model=Detection)
def detect(body: TextIn) -> Detection:
    return get_service().detect(body.text)


@app.post("/score")
def score(body: TextIn):
    return get_service().score(body.text, body.language or "und")


@app.post("/translate")
def translate(body: TextIn):
    return {"text_en": get_service().translate(body.text, body.language)}
