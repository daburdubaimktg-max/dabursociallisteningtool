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

# Market mentions surface mostly in comments ("available in KSA?"), so market tagging
# scans the comment text too — unlike brand tagging, which keys off caption/hashtags.
_MARKET_ALIASES: dict[str, list[str]] = {
    "UAE": ["uae", "dubai", "dxb", "emirates", "abu dhabi"],
    "KSA": ["ksa", "saudi", "riyadh", "jeddah"],
    "Kuwait": ["kuwait", "q8"],
    "Iraq": ["iraq", "baghdad"],
    "Egypt": ["egypt", "cairo", "masr"],
    "Morocco": ["morocco", "maroc", "casablanca"],
    "Libya": ["libya", "tripoli"],
    "Kenya": ["kenya", "nairobi"],
    "Zambia": ["zambia", "lusaka"],
    "Ethiopia": ["ethiopia", "addis"],
    "South Africa": ["south africa", "johannesburg", "cape town"],
}


def tag_brands(record: NormalizedRecord) -> NormalizedRecord:
    haystack = " ".join([record.caption_or_title or "", *(record.hashtags or [])]).lower()
    tags = [
        brand
        for brand, aliases in _BRAND_ALIASES.items()
        if any(alias in haystack for alias in aliases)
    ]
    record.brand_tags = tags or ["other"]
    return record


def tag_markets(record: NormalizedRecord) -> NormalizedRecord:
    haystack = " ".join(
        [
            record.caption_or_title or "",
            *(record.hashtags or []),
            *(c.text_raw or "" for c in record.comments),
        ]
    ).lower()
    tags = [
        market
        for market, aliases in _MARKET_ALIASES.items()
        if any(alias in haystack for alias in aliases)
    ]
    record.market_tags = tags  # may be empty; "untagged" is handled at rollup time
    return record
