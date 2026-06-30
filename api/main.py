"""FastAPI surface for the slice: run a job, read the one gold KPI.

- POST /jobs        run the TikTok collect→detect→score→rollup job for a post URL.
- GET  /kpi/net-sentiment   return the current Net Sentiment Score (sentiment only).

Competitor follower-growth (reach dimension — separate from sentiment, Rule 2):
- POST /growth/seed            load the historical follower series.
- POST /growth/collect         collect a follower reading for a period.
- GET  /growth/leaderboard     follower-gain leaderboard per platform.
- GET  /growth/dashboard.xlsx  download the live multi-sheet Excel dashboard.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from adapters.tiktok.adapter import TikTokAdapter
from adapters.tiktok.provider import default_provider
from core.schema import CollectRequest, InputType, Platform, SentimentLabel
from dashboard_export.excel import workbook_bytes
from growth.models import GrowthPlatform
from growth.pipeline import collect_period, seed_history
from growth.store import GrowthStore
from kpi.growth import leaderboard
from kpi.net_sentiment import net_sentiment_from_labels
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
_GROWTH_STORE = GrowthStore(os.environ.get("GROWTH_DB_PATH", ":memory:"))


class JobRequest(BaseModel):
    url: str
    brands: list[str] = []
    markets: list[str] = []


@app.post("/jobs")
def run(body: JobRequest):
    request = CollectRequest(
        input_type=InputType.post_url,
        target=body.url,
        platform=Platform.tiktok,
        brands=body.brands,
        markets=body.markets,
    )
    adapter = TikTokAdapter(provider=default_provider())
    result = run_job(request, adapter, get_service(), _STORE)
    return result


@app.get("/kpi/net-sentiment")
def net_sentiment():
    labels = [SentimentLabel(v) for v in _STORE.comment_sentiment_labels()]
    net = net_sentiment_from_labels(labels)
    return net


# --- competitor follower-growth (reach dimension; separate from sentiment) --------
class CollectGrowthRequest(BaseModel):
    period: str  # "YYYY-MM"


@app.post("/growth/seed")
def growth_seed():
    n = seed_history(_GROWTH_STORE)
    return {"seeded": n, "snapshots": _GROWTH_STORE.snapshot_count()}


@app.post("/growth/collect")
def growth_collect(body: CollectGrowthRequest):
    written = collect_period(_GROWTH_STORE, body.period)
    return {"period": body.period, "written": written, "snapshots": _GROWTH_STORE.snapshot_count()}


@app.get("/growth/leaderboard")
def growth_leaderboard(platform: str = Query("instagram")):
    rows = leaderboard(_GROWTH_STORE, GrowthPlatform(platform))
    return [r.model_dump() for r in rows]


@app.get("/growth/dashboard.xlsx")
def growth_dashboard():
    # Build live from current store state. Seed history if the store is empty so the
    # endpoint always returns a populated dashboard.
    if _GROWTH_STORE.snapshot_count() == 0:
        seed_history(_GROWTH_STORE)
    data = workbook_bytes(_GROWTH_STORE)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=competitor_growth_dashboard.xlsx"},
    )
