"""StubNLPService — NON-PRODUCTION deterministic NLP for CI / no-GPU environments.

⚠️  This is NOT a real model. It exists so the pipeline runs end-to-end without a GPU.
    Governance (CLAUDE.md §3):
      - feature-flagged; never the default in a production config (see nlp/service.py),
      - every score stamps model_version="stub" so stub records are excludable,
      - it satisfies the same NLPService contract the real transformer service must pass.

Real routing (MARBERT / CAMeLBERT / DarijaBERT / AfroXLMR / NLLB-200) slots in behind
this exact interface later, with zero pipeline changes.
"""

from __future__ import annotations

import hashlib
import re

from core.schema import Sentiment, SentimentLabel
from nlp.contract import Detection, NLPService
from pipeline.text_utils import extract_emojis, has_arabic_script, is_arabizi

MODEL_VERSION = "stub"

# Tiny deterministic sentiment lexicons. A real model replaces this entirely.
_POS = {
    # english
    "love",
    "best",
    "amazing",
    "great",
    "perfect",
    "good",
    "recommend",
    "shine",
    "wonderful",
    "nice",
    # arabizi
    "7elo",
    "helo",
    "7ilo",
    "3ajabni",
    "ajabni",
    "zwin",
    "mzyan",
    "tamam",
}
_NEG = {
    # english
    "fake",
    "terrible",
    "leak",
    "leaks",
    "bad",
    "worst",
    "hate",
    "counterfeit",
    "scam",
    "broken",
    "broke",
    "awful",
    "disappointed",
}
# Arabic is matched by substring (no whitespace tokenization assumptions).
_POS_AR = ["رائع", "أحب", "احب", "ممتاز", "جميل", "أنصح", "انصح", "حلو", "رهيب"]
_NEG_AR = ["سيء", "مزيف", "تقليد", "رديء", "كره", "مقلد", "تسريب"]

_POS_EMOJI = {"😍", "🔥", "❤", "❤️", "✨", "👍", "🥰", "😻"}
_NEG_EMOJI = {"😡", "🤮", "👎", "💔", "😠", "🤢"}


class StubNLPService(NLPService):
    def __init__(self):
        self._translate_cache: dict[str, str] = {}

    # --- detect -----------------------------------------------------------------
    def detect(self, text: str) -> Detection:
        t = (text or "").strip()
        if has_arabic_script(t):
            return Detection(language="ar", dialect="MSA", confidence=0.95)

        if is_arabizi(t):
            # Latin-script Arabic — route to the Arabic/dialect path, NOT English.
            return Detection(language="arabizi", dialect="Levantine", confidence=0.8)

        return Detection(language="en", dialect=None, confidence=0.9)

    # --- score (in original language — Rule 1) ----------------------------------
    def score(self, text: str, language: str) -> Sentiment:
        t = text or ""
        lower = t.lower()
        tokens = set(re.findall(r"[a-z0-9']+", lower))
        emojis = set(extract_emojis(t))

        pos = len(tokens & _POS) + len(emojis & _POS_EMOJI)
        neg = len(tokens & _NEG) + len(emojis & _NEG_EMOJI)
        pos += sum(1 for w in _POS_AR if w in t)
        neg += sum(1 for w in _NEG_AR if w in t)

        total_hits = pos + neg
        if total_hits == 0:
            return Sentiment(
                label=SentimentLabel.neutral,
                score=0.0,
                confidence=0.4,
                model_version=MODEL_VERSION,
            )

        score = (pos - neg) / total_hits
        if score > 0.15:
            label = SentimentLabel.positive
        elif score < -0.15:
            label = SentimentLabel.negative
        else:
            label = SentimentLabel.neutral

        confidence = min(0.95, 0.5 + 0.1 * total_hits)
        return Sentiment(
            label=label,
            score=round(score, 4),
            confidence=round(confidence, 4),
            model_version=MODEL_VERSION,
        )

    # --- translate (display only, cached on text hash) --------------------------
    def translate(self, text: str, source_language: str | None = None) -> str:
        key = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
        if key not in self._translate_cache:
            # Non-production: a real NLLB-200 call replaces this. Marked so it is never
            # mistaken for a real translation.
            self._translate_cache[key] = f"[stub-translation] {text}"
        return self._translate_cache[key]
