"""NLP service contract (CLAUDE.md §3).

This is the single interface the pipeline calls. The deterministic stub AND the future
self-hosted transformer service MUST both satisfy it — `tests/test_nlp_contract.py` is
the executable spec that validates the eventual GPU swap-in against the same behaviour.

Three operations:
  detect(text)    -> Detection(language, dialect, confidence)   incl. Arabizi path
  score(text, language) -> Sentiment(label, score, confidence, model_version)
                           scored IN the original language (Rule 1). NEVER pass text_en.
  translate(text) -> str (text_en) — for human display only, cached on text hash.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from pydantic import BaseModel

from core.schema import Sentiment


class Detection(BaseModel):
    language: str  # e.g. "ar", "en", "arabizi", "sw"
    dialect: Optional[str] = None  # e.g. "Gulf", "Levantine", "Maghrebi", "MSA"
    confidence: float


@runtime_checkable
class NLPService(Protocol):
    def detect(self, text: str) -> Detection: ...

    def score(self, text: str, language: str) -> Sentiment: ...

    def translate(self, text: str, source_language: str | None = None) -> str: ...
