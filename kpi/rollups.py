"""Gold read-set rollups (CLAUDE.md §4) — everything the dashboard reads.

Two load-bearing rules are enforced structurally here:

- Rule 1 (score in language): the word cloud is built from ORIGINAL-language tokens
  (`text_raw`), never from `text_en`. English is a display gloss only.
- Rule 2 (reach ≠ sentiment): sentiment rollups go through `net_sentiment_from_labels`,
  which takes LABELS ONLY — there is no path to fold likes/views/followers into a
  sentiment number. Engagement lives in `volume_summary` / `top_authors`, reported
  side-by-side, never blended.

Every rollup accepts the same `Filters` (brand, market, platform, date, sentiment) so the
dashboard's filter bar drives every view, and `post_explorer` is the shared drill target:
any chart segment maps to a filter set and resolves to its underlying source rows.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Optional

from core.schema import SentimentLabel
from kpi import wordcloud
from kpi.net_sentiment import net_sentiment_from_labels

UNTAGGED = "(untagged)"


@dataclass(frozen=True)
class Filters:
    brand: Optional[str] = None
    market: Optional[str] = None
    platform: Optional[str] = None
    sentiment: Optional[str] = None
    date_from: Optional[str] = None  # YYYY-MM-DD (inclusive)
    date_to: Optional[str] = None  # YYYY-MM-DD (inclusive)


# --- read model: join comments to their post context ------------------------------
def build_items(posts: list[dict], comments: list[dict]) -> list[dict]:
    """Flatten scored comments, inheriting brand/market/url/date from their post."""
    post_by_key = {(p.get("platform"), p.get("post_id")): p for p in posts}
    items = []
    for c in comments:
        post = post_by_key.get((c.get("platform"), c.get("post_id")), {})
        sentiment = c.get("sentiment") or {}
        items.append(
            {
                "platform": c.get("platform"),
                "post_id": c.get("post_id"),
                "comment_id": c.get("comment_id"),
                "url": post.get("url") or "",
                "author": c.get("author"),
                "likes": c.get("likes") or 0,
                "posted_at": c.get("posted_at") or post.get("posted_at"),
                "brands": post.get("brand_tags") or ["other"],
                "markets": post.get("market_tags") or [],
                "sentiment": sentiment.get("label"),
                "score": sentiment.get("score"),
                "confidence": sentiment.get("confidence"),
                "model_version": sentiment.get("model_version"),
                "language": c.get("detected_language"),
                "dialect": c.get("detected_dialect"),
                "text_raw": c.get("text_raw") or "",
                "text_en": c.get("text_en") or "",
            }
        )
    return items


def build_post_items(posts: list[dict]) -> list[dict]:
    """Normalize post records to the same filterable shape as comment items."""
    return [
        {
            "platform": p.get("platform"),
            "post_id": p.get("post_id"),
            "url": p.get("url") or "",
            "author": p.get("author_handle"),
            "brands": p.get("brand_tags") or ["other"],
            "markets": p.get("market_tags") or [],
            "posted_at": p.get("posted_at"),
            "hashtags": p.get("hashtags") or [],
            "metrics": p.get("metrics") or {},
            "sentiment": (p.get("sentiment") or {}).get("label"),
        }
        for p in posts
    ]


def _date(value: Optional[str]) -> str:
    return (value or "")[:10]


def _passes(item: dict, f: Filters, *, use_sentiment: bool = True) -> bool:
    if f.platform and item.get("platform") != f.platform:
        return False
    if f.brand and f.brand not in (item.get("brands") or []):
        return False
    if f.market and f.market not in (item.get("markets") or []):
        return False
    if use_sentiment and f.sentiment and item.get("sentiment") != f.sentiment:
        return False
    d = _date(item.get("posted_at"))
    if f.date_from and d and d < f.date_from:
        return False
    if f.date_to and d and d > f.date_to:
        return False
    return True


def apply_filters(items: list[dict], f: Filters, *, use_sentiment: bool = True) -> list[dict]:
    return [it for it in items if _passes(it, f, use_sentiment=use_sentiment)]


def _split(items: list[dict]) -> dict:
    """Sentiment split via the canonical KPI — labels only (Rule 2)."""
    labels = [SentimentLabel(it["sentiment"]) for it in items if it.get("sentiment")]
    return net_sentiment_from_labels(labels).model_dump()


def _grouped_split(items: list[dict], key: str) -> list[dict]:
    """Split by a multi-valued tag dimension (brands/markets) or single (platform)."""
    buckets: dict[str, list[dict]] = {}
    for it in items:
        values = it.get(key)
        if isinstance(values, list):
            keys = values or [UNTAGGED]
        else:
            keys = [values or UNTAGGED]
        for k in keys:
            buckets.setdefault(k, []).append(it)
    rows = [{"key": k, **_split(v)} for k, v in buckets.items()]
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows


# --- KPI views --------------------------------------------------------------------
def sentiment_split(items: list[dict], f: Filters) -> dict:
    rows = apply_filters(items, f)
    return {
        "overall": _split(rows),
        "by_platform": _grouped_split(rows, "platform"),
        "by_brand": _grouped_split(rows, "brands"),
        "by_market": _grouped_split(rows, "markets"),
    }


def net_sentiment_trend(items: list[dict], f: Filters) -> list[dict]:
    """Net Sentiment over time, bucketed by day (CLAUDE.md §4)."""
    rows = apply_filters(items, f)
    by_day: dict[str, list[dict]] = {}
    for it in rows:
        day = _date(it.get("posted_at"))
        if day:
            by_day.setdefault(day, []).append(it)
    out = [{"date": day, **_split(v)} for day, v in sorted(by_day.items())]
    return out


def share_of_voice(items: list[dict], f: Filters) -> list[dict]:
    """SoV = a brand's conversation volume ÷ total tracked mentions (volume, not sentiment)."""
    rows = apply_filters(items, f)
    mentions: Counter[str] = Counter()
    for it in rows:
        for brand in it.get("brands") or [UNTAGGED]:
            mentions[brand] += 1
    total = sum(mentions.values())
    out = [
        {"brand": b, "mentions": n, "share": round(n / total, 4) if total else 0.0}
        for b, n in mentions.most_common()
    ]
    return out


def word_cloud(items: list[dict], f: Filters, sentiment: str = "all", limit: int = 60) -> dict:
    """Sentiment-segmented cloud from ORIGINAL-language tokens (Rule 1).

    `sentiment` ∈ {all, positive, neutral, negative} selects the segment. The toggle is
    independent of the global sentiment filter so the cloud can be sliced on its own.
    """
    rows = apply_filters(items, f, use_sentiment=False)
    if sentiment != "all":
        rows = [it for it in rows if it.get("sentiment") == sentiment]

    counts: Counter[str] = Counter()
    for it in rows:
        counts.update(wordcloud.tokenize(it.get("text_raw", "")))

    terms = [
        {
            "term": term,
            "count": n,
            "gloss": wordcloud.gloss_for(term),
            "rtl": wordcloud.is_rtl(term),
        }
        for term, n in counts.most_common(limit)
    ]
    return {"sentiment": sentiment, "terms": terms}


def top_hashtags(post_items: list[dict], f: Filters, limit: int = 20) -> list[dict]:
    rows = apply_filters(post_items, f, use_sentiment=False)
    counts: Counter[str] = Counter()
    for p in rows:
        counts.update(h.lower() for h in (p.get("hashtags") or []))
    return [{"hashtag": h, "count": n} for h, n in counts.most_common(limit)]


def top_authors(items: list[dict], f: Filters, limit: int = 20) -> list[dict]:
    """Authors by engagement contribution (reach view — kept separate from sentiment)."""
    rows = apply_filters(items, f)
    agg: dict[str, dict] = {}
    for it in rows:
        author = it.get("author") or "unknown"
        a = agg.setdefault(author, {"author": author, "comments": 0, "total_likes": 0})
        a["comments"] += 1
        a["total_likes"] += it.get("likes") or 0
    out = sorted(agg.values(), key=lambda a: (a["total_likes"], a["comments"]), reverse=True)
    return out[:limit]


def language_distribution(items: list[dict], f: Filters) -> dict:
    rows = apply_filters(items, f)
    counts = Counter(it.get("language") or "unknown" for it in rows)
    total = sum(counts.values())
    distribution = [
        {"language": lang, "count": n, "share": round(n / total, 4) if total else 0.0}
        for lang, n in counts.most_common()
    ]
    arabizi = counts.get("arabizi", 0)
    return {
        "distribution": distribution,
        "arabizi_share": round(arabizi / total, 4) if total else 0.0,
        "total": total,
    }


def post_explorer(items: list[dict], f: Filters, limit: int = 500) -> list[dict]:
    """The shared drill target: scored rows with English display text + source link."""
    rows = apply_filters(items, f)
    rows.sort(key=lambda it: it.get("posted_at") or "", reverse=True)
    return rows[:limit]


def volume_summary(post_items: list[dict], items: list[dict], f: Filters) -> dict:
    """Reach section (CLAUDE.md §4): volumes + total engagement, never fused with sentiment."""
    post_rows = apply_filters(post_items, f, use_sentiment=False)
    comment_rows = apply_filters(items, f)
    engagement = Counter()
    for p in post_rows:
        m = p.get("metrics") or {}
        for k in ("likes", "comments_count", "views", "shares", "saves"):
            engagement[k] += m.get(k) or 0
    return {
        "posts": len(post_rows),
        "comments": len(comment_rows),
        "engagement": dict(engagement),
    }


def filter_options(post_items: list[dict], items: list[dict]) -> dict:
    """Distinct values to populate the filter bar."""
    brands, markets, platforms, languages, dates = set(), set(), set(), set(), []
    for it in items:
        brands.update(it.get("brands") or [])
        markets.update(it.get("markets") or [])
        if it.get("platform"):
            platforms.add(it["platform"])
        if it.get("language"):
            languages.add(it["language"])
        d = _date(it.get("posted_at"))
        if d:
            dates.append(d)
    for p in post_items:
        brands.update(p.get("brands") or [])
        markets.update(p.get("markets") or [])
        if p.get("platform"):
            platforms.add(p["platform"])
    return {
        "brands": sorted(brands),
        "markets": sorted(markets),
        "platforms": sorted(platforms),
        "languages": sorted(languages),
        "sentiments": ["positive", "neutral", "negative"],
        "date_min": min(dates) if dates else None,
        "date_max": max(dates) if dates else None,
    }
