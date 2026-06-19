"""Small, dependency-free text helpers shared across the pipeline."""

from __future__ import annotations

import re

_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)

# Covers the common emoji blocks well enough for the slice (no external dep).
_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"  # symbols, pictographs, supplemental
    "\U00002600-\U000027bf"  # misc symbols + dingbats
    "\U0001f1e6-\U0001f1ff"  # regional indicators
    "]",
    flags=re.UNICODE,
)

_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿ]")

# Arabic normalization (CLAUDE.md §4 word cloud): strip diacritics/tatweel and unify
# alef + ya variants so surface forms collapse to one token.
_AR_DIACRITICS_RE = re.compile(r"[ً-ٰٟـ]")
_AR_ALEF_RE = re.compile(r"[آأإٱ]")  # آ أ إ ٱ → ا


def extract_hashtags(text: str) -> list[str]:
    return _HASHTAG_RE.findall(text or "")


def extract_emojis(text: str) -> list[str]:
    return _EMOJI_RE.findall(text or "")


def has_arabic_script(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))


def normalize_arabic(text: str) -> str:
    """Strip diacritics + tatweel, unify alef variants → ا and alef-maqsura ى → ي."""
    t = _AR_DIACRITICS_RE.sub("", text or "")
    t = _AR_ALEF_RE.sub("ا", t)
    return t.replace("ى", "ي")
