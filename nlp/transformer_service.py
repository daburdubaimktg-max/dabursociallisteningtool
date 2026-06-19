"""TransformerNLPService — the real, self-hosted NLP backend (CLAUDE.md §3).

This satisfies the SAME `NLPService` contract as the stub, so it slots in behind the
pipeline with zero pipeline changes and is validated by `tests/test_nlp_contract.py`.

Two load-bearing rules are encoded here:
  - Rule 1 (score in language): detection runs first, then sentiment is scored on the
    ORIGINAL text with a language/dialect-native model. We NEVER translate before scoring.
  - Arabizi (Latin-script Arabic) is routed to the Arabic model, never to a generic LID
    model that would call it English/French.

Heavy deps (`transformers`, `torch`) are imported lazily so importing this module — and
running the rest of the test suite — never requires a GPU stack. Models are pinned via
env so weights are swappable without code changes and read from the model registry in
production. CPU-first today; the GPU swap-in is the same class with bigger hardware.

`translate` is intentionally a display-only passthrough until the NLLB-200 / GPU slice
lands (see CLAUDE.md §3); it is clearly marked so it is never mistaken for a real MT.

NOTE ON MODELS: the default model ids below are MARBERT-family / multilingual sentiment
checkpoints chosen as sensible defaults. They are env-overridable and MUST be validated
against the frozen held-out MENA eval set before any production reporting — that accuracy
/F1 gate is deferred until we have labeled data.
"""

from __future__ import annotations

import hashlib
import os
import threading
from typing import TYPE_CHECKING, Optional

from core.schema import Sentiment, SentimentLabel
from nlp.contract import Detection, NLPService
from pipeline.text_utils import has_arabic_script, is_arabizi

if TYPE_CHECKING:  # pragma: no cover - typing only
    from transformers import Pipeline

# Stamped on every record this backend scores (audit / rollback / attribution, §3).
# Carries the resolved Arabic model id so reports can attribute and exclude by version.
_MODEL_FAMILY = "marbert"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


# --- model routing config (env-overridable; pinned in the registry for prod) ---------
# Arabic (MSA + dialectal) sentiment — MARBERT-family by default (Rule 1).
AR_SENTIMENT_MODEL = _env("NLP_AR_SENTIMENT_MODEL", "Ammar-alhaj-ali/arabic-MARBERT-sentiment")
# Maghrebi / Darija routing override (DarijaBERT etc.); empty = fall back to AR model.
AR_MAGHREBI_SENTIMENT_MODEL = _env("NLP_AR_MAGHREBI_SENTIMENT_MODEL", "")
# English + other Latin — multilingual social-media XLM-R sentiment (CLAUDE.md §3).
EN_SENTIMENT_MODEL = _env("NLP_EN_SENTIMENT_MODEL", "cardiffnlp/twitter-xlm-roberta-base-sentiment")
# Language ID for Latin-script text (Arabic script + Arabizi are handled by heuristics).
LID_MODEL = _env("NLP_LID_MODEL", "papluca/xlm-roberta-base-language-detection")
# Optional Arabic dialect classifier; empty = report dialect as unknown (None).
AR_DIALECT_MODEL = _env("NLP_AR_DIALECT_MODEL", "")

_MAGHREBI = {"maghrebi", "darija", "moroccan", "algerian", "tunisian"}


def _normalize_label(raw: str) -> SentimentLabel:
    """Map a model's label string onto our 3-class enum. Fails LOUDLY on opaque labels
    (e.g. bare ``LABEL_0``) so a mis-mapped checkpoint can never silently skew reports."""
    label = (raw or "").strip().lower()
    if "pos" in label:
        return SentimentLabel.positive
    if "neg" in label:
        return SentimentLabel.negative
    if "neu" in label:
        return SentimentLabel.neutral
    raise ValueError(
        f"Cannot map sentiment label {raw!r} to positive/neutral/negative. "
        "Configure an explicit label map for this checkpoint."
    )


class TransformerNLPService(NLPService):
    """Real NLP backend. Lazy-loads and caches one pipeline per model id."""

    def __init__(self) -> None:
        self._pipelines: dict[str, "Pipeline"] = {}
        self._lock = threading.Lock()
        self._translate_cache: dict[str, str] = {}

    # --- lazy pipeline loading --------------------------------------------------
    def _pipeline(self, task: str, model_id: str) -> "Pipeline":
        key = f"{task}:{model_id}"
        cached = self._pipelines.get(key)
        if cached is not None:
            return cached
        with self._lock:
            cached = self._pipelines.get(key)
            if cached is not None:
                return cached
            # Imported lazily: the rest of the suite must run without torch installed.
            from transformers import pipeline

            # device=-1 → CPU. The GPU swap-in only changes this line's environment.
            pipe = pipeline(task=task, model=model_id, tokenizer=model_id, device=-1)
            self._pipelines[key] = pipe
            return pipe

    # --- detect (runs BEFORE scoring — Rule 1) ----------------------------------
    def detect(self, text: str) -> Detection:
        t = (text or "").strip()
        if not t:
            return Detection(language="und", dialect=None, confidence=0.0)

        if has_arabic_script(t):
            dialect, conf = self._detect_dialect(t)
            return Detection(language="ar", dialect=dialect, confidence=conf)

        if is_arabizi(t):
            # Latin-script Arabic → Arabic path, never English (load-bearing).
            return Detection(language="arabizi", dialect=None, confidence=0.8)

        out = self._pipeline("text-classification", LID_MODEL)(t, truncation=True)[0]
        return Detection(language=str(out["label"]), dialect=None, confidence=float(out["score"]))

    def _detect_dialect(self, text: str) -> tuple[Optional[str], float]:
        if not AR_DIALECT_MODEL:
            return None, 0.9  # script is unambiguous; dialect simply not yet resolved
        out = self._pipeline("text-classification", AR_DIALECT_MODEL)(text, truncation=True)[0]
        return str(out["label"]), float(out["score"])

    # --- score (in original language — Rule 1) ----------------------------------
    def score(self, text: str, language: str) -> Sentiment:
        return self.score_batch([text], language)[0]

    def score_batch(
        self, texts: list[str], language: str, dialect: str | None = None
    ) -> list[Sentiment]:
        """Batched inference — throughput comes from batching, not bigger hardware (§3)."""
        model_id = self._resolve_sentiment_model(language, dialect)
        model_version = f"{_MODEL_FAMILY}:{model_id}"
        pipe = self._pipeline("text-classification", model_id)
        results = []
        for out in pipe([t or "" for t in texts], truncation=True, batch_size=16):
            prob = float(out["score"])
            label = _normalize_label(str(out["label"]))
            if label is SentimentLabel.positive:
                signed = prob
            elif label is SentimentLabel.negative:
                signed = -prob
            else:
                signed = 0.0
            results.append(
                Sentiment(
                    label=label,
                    score=round(signed, 4),
                    confidence=round(prob, 4),
                    model_version=model_version,
                )
            )
        return results

    def _resolve_sentiment_model(self, language: str, dialect: str | None) -> str:
        lang = (language or "").lower()
        if lang in {"ar", "arabizi"}:
            if AR_MAGHREBI_SENTIMENT_MODEL and (dialect or "").lower() in _MAGHREBI:
                return AR_MAGHREBI_SENTIMENT_MODEL
            return AR_SENTIMENT_MODEL
        # English + other Latin scripts use the multilingual sentiment model.
        return EN_SENTIMENT_MODEL

    # --- translate (display only; DEFERRED to the GPU/NLLB slice) ----------------
    def translate(self, text: str, source_language: str | None = None) -> str:
        key = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
        if key not in self._translate_cache:
            # Real MT (NLLB-200) lands with the GPU slice. Until then this is an explicit
            # display-only passthrough — marked so it is never mistaken for a translation.
            self._translate_cache[key] = f"[mt-pending] {text}"
        return self._translate_cache[key]
