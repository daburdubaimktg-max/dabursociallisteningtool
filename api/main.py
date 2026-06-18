"""FastAPI surface for the slice: run a job, read the one gold KPI.

- POST /jobs        run the TikTok collect→detect→score→rollup job for a post URL.
- GET  /kpi/net-sentiment   return the current Net Sentiment Score (sentiment only).
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from adapters.tiktok.adapter import TikTokAdapter
from adapters.tiktok.provider import default_provider
from core.schema import CollectRequest, InputType, Platform, SentimentLabel
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
