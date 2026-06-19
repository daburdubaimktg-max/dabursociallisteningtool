"""Pipeline orchestration (CLAUDE.md §2):

    collect → normalize → detect language → translate (display) → score (in-language)
            → enrich → write silver → roll up gold

LOAD-BEARING (Rule 1): comments are scored on `text_raw` (original language). `text_en`
is produced for display only and is NEVER passed to `score()`.
"""

from __future__ import annotations

from pydantic import BaseModel

from adapters.base import Adapter
from core.schema import CollectRequest, NormalizedRecord
from kpi.net_sentiment import NetSentiment, net_sentiment_from_labels
from nlp.contract import NLPService
from pipeline.enrich import tag_brands, tag_markets
from pipeline.store import Store
from core.schema import SentimentLabel


class JobResult(BaseModel):
    posts: int
    comments: int
    net_sentiment: NetSentiment


def _enrich_text(text: str, nlp: NLPService):
    """Detect → translate-for-display → score-in-language. Returns the three results."""
    detection = nlp.detect(text)
    text_en = nlp.translate(text, detection.language)  # display only
    sentiment = nlp.score(text, detection.language)  # scored on ORIGINAL text (Rule 1)
    return detection, text_en, sentiment


def process_record(record: NormalizedRecord, nlp: NLPService) -> NormalizedRecord:
    # Post caption.
    if record.caption_or_title:
        det, text_en, sent = _enrich_text(record.caption_or_title, nlp)
        record.detected_language = det.language
        record.detected_dialect = det.dialect
        record.text_en = text_en
        record.sentiment = sent

    # Comments.
    for c in record.comments:
        det, text_en, sent = _enrich_text(c.text_raw, nlp)
        c.detected_language = det.language
        c.detected_dialect = det.dialect
        c.text_en = text_en
        c.sentiment = sent

    return tag_markets(tag_brands(record))


def run_job(
    request: CollectRequest,
    adapter: Adapter,
    nlp: NLPService,
    store: Store,
) -> JobResult:
    # Bronze: persist raw payloads immutably for re-processing.
    for raw in adapter.raw_payloads(request):
        post_id = str(raw.get("id"))
        # collected_at is stamped per-record during normalization; use a marker here.
        store.write_bronze(request.platform.value, post_id, raw, collected_at="")

    # Silver: normalize → enrich → persist (idempotent upserts).
    for record in adapter.collect(request):
        process_record(record, nlp)
        store.write_silver(record)

    # Gold: roll up the KPI from sentiment labels only (no engagement — Rule 2).
    labels = [SentimentLabel(v) for v in store.comment_sentiment_labels()]
    net = net_sentiment_from_labels(labels)

    return JobResult(posts=store.post_count(), comments=store.comment_count(), net_sentiment=net)
