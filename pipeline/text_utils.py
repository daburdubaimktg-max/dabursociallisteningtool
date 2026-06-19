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

# Latin script with Arabic-chat numeral substitution (3=ع, 7=ح, 2=ء, 5=خ, 9=ق) — the
# Arabizi signal that standard language-ID misreads as English/French (CLAUDE.md §3).
_ARABIZI_NUM_RE = re.compile(r"[a-z][235679]|[235679][a-z]")
_ARABIZI_TOKENS = {"wallah", "shu", "akhbarak", "ktir", "kteer", "ya", "habibi", "yalla"}


def extract_hashtags(text: str) -> list[str]:
    return _HASHTAG_RE.findall(text or "")


def extract_emojis(text: str) -> list[str]:
    return _EMOJI_RE.findall(text or "")


def has_arabic_script(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))


def is_arabizi(text: str) -> bool:
    """Latin-script Arabic (chat-alphabet). Load-bearing: this MUST route to the Arabic
    sentiment path, never be mislabeled English/French by a generic LID model (Rule 1)."""
    lower = (text or "").lower()
    tokens = set(re.findall(r"[a-z0-9']+", lower))
    return bool(_ARABIZI_NUM_RE.search(lower) or (tokens & _ARABIZI_TOKENS))
