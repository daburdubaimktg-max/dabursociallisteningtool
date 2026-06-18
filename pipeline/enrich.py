"""Enrichment hooks. Minimal for the first slice — extended in later slices.

For the slice this only does light brand tagging from a seed taxonomy, so the path
exists and is testable. Spam/bot/counterfeit/influencer enrichment lands later.
"""

from __future__ import annotations

from core.schema import NormalizedRecord

# Seed taxonomy (config-as-data target: this moves to an editable lookup table).
_BRAND_ALIASES: dict[str, list[str]] = {
    "Vatika": ["vatika"],
    "Dabur Amla": ["amla", "dabur amla"],
    "ORS": ["ors"],
    "Fem": ["fem"],
    "Hobby": ["hobby"],
    "Dabur Herb'l": ["herbl", "herb'l", "dabur herb'l"],
}


def tag_brands(record: NormalizedRecord) -> NormalizedRecord:
    haystack = " ".join(
        [record.caption_or_title or "", *(record.hashtags or [])]
    ).lower()
    tags = [
        brand
        for brand, aliases in _BRAND_ALIASES.items()
        if any(alias in haystack for alias in aliases)
    ]
    record.brand_tags = tags or ["other"]
    return record
