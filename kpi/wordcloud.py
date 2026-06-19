"""Word-cloud text processing (CLAUDE.md §4).

Built from ORIGINAL-language tokens (never the English translation): Arabic normalization
(strip diacritics, unify alef/ya — see pipeline.text_utils.normalize_arabic) + Arabic and
English stopword removal, with an English gloss surfaced on hover. RTL is flagged per term
so the dashboard can pick an RTL-aware font.
"""

from __future__ import annotations

import re

from pipeline.text_utils import has_arabic_script, normalize_arabic

# Token = starts with a letter (Arabic or Latin), may contain internal digits so Arabizi
# chat-numerals survive (7elo, 3ajabni). Pure numbers / punctuation are dropped.
_TOKEN_RE = re.compile(r"[A-Za-z؀-ۿ][A-Za-z0-9؀-ۿ']*")

_EN_STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "this",
    "that",
    "it",
    "in",
    "on",
    "of",
    "to",
    "and",
    "or",
    "for",
    "with",
    "so",
    "my",
    "i",
    "you",
    "we",
    "they",
    "was",
    "were",
    "be",
    "at",
    "as",
    "but",
    "not",
    "no",
    "do",
    "does",
    "did",
    "have",
    "has",
    "had",
    "will",
    "when",
    "what",
    "how",
    "why",
    "where",
    "from",
    "by",
    "all",
    "if",
    "me",
    "your",
    "their",
    "its",
}

# Arabic stopwords in NORMALIZED form (alef/ya unified) so they match normalized tokens.
_AR_STOPWORDS = {
    "من",
    "في",
    "علي",
    "الي",
    "عن",
    "مع",
    "هذا",
    "هذه",
    "ذلك",
    "التي",
    "الذي",
    "ما",
    "لا",
    "و",
    "يا",
    "انا",
    "انت",
    "هو",
    "هي",
    "جدا",
    "كان",
    "قد",
    "كل",
    "بعد",
    "عند",
    "بين",
    "ان",
    "او",
    "ثم",
    "فيه",
    "به",
    "بشده",
    "هنا",
}

# Seed English gloss for common MENA sentiment terms (config-as-data target). Keyed by the
# normalized original-language token; absent terms simply have no gloss (hover shows term).
_GLOSS: dict[str, str] = {
    # Arabic
    "رائع": "wonderful",
    "ممتاز": "excellent",
    "جميل": "beautiful",
    "حلو": "nice",
    "رهيب": "awesome",
    "منتج": "product",
    "مزيف": "fake",
    "تقليد": "counterfeit",
    "سيء": "bad",
    "رديء": "poor",
    "تسريب": "leak",
    "احب": "love",
    "احبه": "love it",
    # Arabizi / Darija
    "7elo": "nice",
    "7elwa": "nice",
    "3ajabni": "i liked it",
    "mzyan": "good (Darija)",
    "ktir": "a lot",
    "wallah": "i swear",
    "rou7a": "smell",
    "zwin": "nice (Darija)",
    # English
    "love": "love",
    "best": "best",
    "amazing": "amazing",
    "fake": "fake",
    "leaks": "leak",
    "broken": "broken",
    "disappointed": "disappointed",
    "terrible": "terrible",
    "available": "available",
}


def _normalize_token(token: str) -> str:
    if has_arabic_script(token):
        return normalize_arabic(token)
    return token.lower()


def is_stopword(token: str) -> bool:
    return token in _EN_STOPWORDS or token in _AR_STOPWORDS


def tokenize(text: str) -> list[str]:
    """Normalized, stopword-filtered, original-language tokens (length ≥ 2)."""
    out = []
    for raw in _TOKEN_RE.findall(text or ""):
        tok = _normalize_token(raw)
        if len(tok) >= 2 and not is_stopword(tok):
            out.append(tok)
    return out


def gloss_for(token: str) -> str | None:
    return _GLOSS.get(token)


def is_rtl(token: str) -> bool:
    return has_arabic_script(token)
