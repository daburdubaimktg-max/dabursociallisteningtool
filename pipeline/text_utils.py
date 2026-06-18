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


def extract_hashtags(text: str) -> list[str]:
    return _HASHTAG_RE.findall(text or "")


def extract_emojis(text: str) -> list[str]:
    return _EMOJI_RE.findall(text or "")


def has_arabic_script(text: str) -> bool:
    return bool(_ARABIC_RE.search(text or ""))
