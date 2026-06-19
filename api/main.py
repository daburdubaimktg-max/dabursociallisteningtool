"""FastAPI surface for the dashboard read-set (CLAUDE.md §4, §7).

Job control:
- POST /jobs            run a collect→detect→score→rollup job for a post URL (per platform).
- POST /seed            populate the store from the recorded fixtures (real pipeline, no
                        mock data) so the dashboard has something to read on first load.

Read-set (all accept the same filters: brand, market, platform, sentiment, date_from,
date_to — every view is filterable, and the post explorer is the shared drill target):
- GET /filters                 distinct filter values + date range
- GET /kpi/volume              reach: volumes + total engagement (separate from sentiment)
- GET /kpi/sentiment-split     overall + by platform / brand / market
- GET /kpi/net-sentiment       overall Net Sentiment (filtered)
- GET /kpi/net-sentiment-trend Net Sentiment over time (by day)
- GET /kpi/share-of-voice      brand share of conversation volume
- GET /kpi/word-cloud          sentiment-segmented, original-language tokens + EN gloss
- GET /kpi/top-hashtags
- GET /kpi/top-authors         by engagement contribution (reach)
- GET /kpi/language-distribution  incl. Arabizi share
- GET /posts                   scored post-explorer rows (drill target)
"""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from adapters.base import Adapter
from core.schema import CollectRequest, InputType, Platform, SentimentLabel
from kpi import rollups
from kpi.net_sentiment import net_sentiment_from_labels
from kpi.rollups import Filters
from nlp.service import get_service
from pipeline.run import run_job
from pipeline.store import Store

app = FastAPI(title="Dabur Social Listening API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STORE = Store(os.environ.get("DB_PATH", ":memory:"))

# Recorded-fixture jobs used to seed the store with real pipeline output (no mock data).
# Platform-agnostic by design: as each adapter lands (Instagram = PR #3, then YouTube/…),
# add its fixture URL here and it flows into every view automatically.
_SEED_JOBS = [
    (Platform.tiktok, "https://www.tiktok.com/@vatika.mena/video/7298451200000000001"),
]


def _adapter_for(platform: Platform) -> Adapter:
    """Pick the adapter + its env-gated provider (live if APIFY_TOKEN, else fixture).

    Instagram and later platforms register here the same way once their adapters merge;
    the read-set downstream is unchanged because it is platform-agnostic.
    """
    from adapters.tiktok.adapter import TikTokAdapter
    from adapters.tiktok.provider import default_provider

    return TikTokAdapter(provider=default_provider())


# --- shared filter dependency + read model ----------------------------------------
def _filters(
    brand: str | None = Query(None),
    market: str | None = Query(None),
    platform: str | None = Query(None),
    sentiment: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
) -> Filters:
    return Filters(
        brand=brand,
        market=market,
        platform=platform,
        sentiment=sentiment,
        date_from=date_from,
        date_to=date_to,
    )


def _read_model() -> tuple[list[dict], list[dict]]:
    """(comment items, post items) — the two flat lists every rollup consumes."""
    posts = _STORE.load_posts()
    comments = _STORE.load_comments()
    items = rollups.build_items(posts, comments)
    post_items = rollups.build_post_items(posts)
    return items, post_items


# --- job control ------------------------------------------------------------------
class JobRequest(BaseModel):
    url: str
    platform: Platform = Platform.tiktok
    brands: list[str] = []
    markets: list[str] = []


@app.post("/jobs")
def run(body: JobRequest):
    request = CollectRequest(
        input_type=InputType.post_url,
        target=body.url,
        platform=body.platform,
        brands=body.brands,
        markets=body.markets,
    )
    return run_job(request, _adapter_for(body.platform), get_service(), _STORE)


@app.post("/seed")
def seed():
    """Run the recorded fixtures through the real pipeline to populate the store."""
    for platform, url in _SEED_JOBS:
        request = CollectRequest(input_type=InputType.post_url, target=url, platform=platform)
        run_job(request, _adapter_for(platform), get_service(), _STORE)
    return {"seeded": [p.value for p, _ in _SEED_JOBS], "posts": _STORE.post_count()}


# --- read-set ---------------------------------------------------------------------
@app.get("/filters")
def filters():
    items, post_items = _read_model()
    return rollups.filter_options(post_items, items)


@app.get("/kpi/volume")
def volume(f: Filters = Depends(_filters)):
    items, post_items = _read_model()
    return rollups.volume_summary(post_items, items, f)


@app.get("/kpi/sentiment-split")
def sentiment_split(f: Filters = Depends(_filters)):
    items, _ = _read_model()
    return rollups.sentiment_split(items, f)


@app.get("/kpi/net-sentiment")
def net_sentiment(f: Filters = Depends(_filters)):
    items, _ = _read_model()
    rows = rollups.apply_filters(items, f)
    labels = [SentimentLabel(it["sentiment"]) for it in rows if it.get("sentiment")]
    return net_sentiment_from_labels(labels)


@app.get("/kpi/net-sentiment-trend")
def net_sentiment_trend(f: Filters = Depends(_filters)):
    items, _ = _read_model()
    return rollups.net_sentiment_trend(items, f)


@app.get("/kpi/share-of-voice")
def share_of_voice(f: Filters = Depends(_filters)):
    items, _ = _read_model()
    return rollups.share_of_voice(items, f)


@app.get("/kpi/word-cloud")
def word_cloud(sentiment_segment: str = "all", f: Filters = Depends(_filters)):
    items, _ = _read_model()
    return rollups.word_cloud(items, f, sentiment=sentiment_segment)


@app.get("/kpi/top-hashtags")
def top_hashtags(f: Filters = Depends(_filters)):
    _, post_items = _read_model()
    return rollups.top_hashtags(post_items, f)


@app.get("/kpi/top-authors")
def top_authors(f: Filters = Depends(_filters)):
    items, _ = _read_model()
    return rollups.top_authors(items, f)


@app.get("/kpi/language-distribution")
def language_distribution(f: Filters = Depends(_filters)):
    items, _ = _read_model()
    return rollups.language_distribution(items, f)


@app.get("/posts")
def posts(f: Filters = Depends(_filters)):
    items, _ = _read_model()
    return rollups.post_explorer(items, f)
