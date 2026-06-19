"""Gold read-set rollups (CLAUDE.md §4): the dashboard's data layer.

Drives the recorded TikTok fixture through the real pipeline into a store, then asserts
each KPI view, the shared filter/drill behaviour, and the two load-bearing rules (word
cloud built from original language; reach never fused into a sentiment number).

The rollups are platform-agnostic — they aggregate whatever is in the store — so the same
assertions scale across platforms as more adapters (Instagram, …) land and seed data.
"""

import inspect

from adapters.tiktok.adapter import TikTokAdapter
from adapters.tiktok.provider import FixtureProvider
from core.schema import CollectRequest, InputType, Platform
from kpi import rollups
from kpi.rollups import Filters
from nlp.stub import StubNLPService
from pipeline.run import run_job
from pipeline.store import Store

URL = "https://www.tiktok.com/@vatika.mena/video/7298451200000000001"


def _seeded_store() -> Store:
    store = Store(":memory:")
    req = CollectRequest(input_type=InputType.post_url, target=URL, platform=Platform.tiktok)
    run_job(req, TikTokAdapter(provider=FixtureProvider()), StubNLPService(), store)
    return store


def _model():
    store = _seeded_store()
    posts = store.load_posts()
    comments = store.load_comments()
    return rollups.build_items(posts, comments), rollups.build_post_items(posts)


# --- sentiment split --------------------------------------------------------------
def test_sentiment_split_overall_and_grouped():
    items, _ = _model()
    split = rollups.sentiment_split(items, Filters())

    # TikTok fixture: 3 positive, 1 neutral, 1 negative → net (3−1)/5 = 0.4.
    assert (
        split["overall"]["positive"],
        split["overall"]["neutral"],
        split["overall"]["negative"],
        split["overall"]["total"],
    ) == (3, 1, 1, 5)
    assert split["overall"]["net_score"] == 0.4

    assert {r["key"] for r in split["by_platform"]} == {"tiktok"}
    assert "Vatika" in {r["key"] for r in split["by_brand"]}
    assert "UAE" in {r["key"] for r in split["by_market"]}


def test_platform_filter_narrows_view():
    items, _ = _model()
    assert rollups.sentiment_split(items, Filters(platform="tiktok"))["overall"]["total"] == 5
    assert rollups.sentiment_split(items, Filters(platform="reddit"))["overall"]["total"] == 0


def test_brand_and_market_filters():
    items, _ = _model()
    assert rollups.sentiment_split(items, Filters(brand="Vatika"))["overall"]["total"] == 5
    assert rollups.sentiment_split(items, Filters(market="UAE"))["overall"]["total"] == 5
    assert rollups.sentiment_split(items, Filters(market="KSA"))["overall"]["total"] == 0


# --- net sentiment over time ------------------------------------------------------
def test_net_sentiment_trend_buckets_by_day():
    items, _ = _model()
    trend = rollups.net_sentiment_trend(items, Filters())
    days = [b["date"] for b in trend]
    assert days == sorted(days)  # chronological
    assert "2026-06-10" in days
    assert all(-1.0 <= b["net_score"] <= 1.0 for b in trend)


# --- share of voice (volume, not sentiment) ---------------------------------------
def test_share_of_voice_sums_to_one():
    items, _ = _model()
    sov = rollups.share_of_voice(items, Filters())
    assert "Vatika" in {r["brand"] for r in sov}
    assert abs(sum(r["share"] for r in sov) - 1.0) < 1e-6


# --- word cloud: original language, segmented, glossed ----------------------------
def test_word_cloud_positive_segment_from_original_language():
    items, _ = _model()
    cloud = rollups.word_cloud(items, Filters(), sentiment="positive")
    terms = {t["term"]: t for t in cloud["terms"]}

    assert "love" in terms  # English positive token present in positive segment
    # Built from text_raw, NOT text_en (Rule 1): the stub-translation marker never leaks.
    assert all("stub-translation" not in t["term"] for t in cloud["terms"])
    # An Arabic (RTL) term from the positive Arabic comment is present and flagged RTL.
    assert any(t["rtl"] for t in cloud["terms"])
    assert terms["love"]["gloss"] == "love"  # gloss surfaced where known


def test_word_cloud_segments_differ():
    items, _ = _model()
    pos = {t["term"] for t in rollups.word_cloud(items, Filters(), "positive")["terms"]}
    neg = {t["term"] for t in rollups.word_cloud(items, Filters(), "negative")["terms"]}
    assert "fake" in neg and "fake" not in pos


# --- language distribution incl. Arabizi share ------------------------------------
def test_language_distribution_and_arabizi_share():
    items, _ = _model()
    dist = rollups.language_distribution(items, Filters())
    assert {"ar", "arabizi", "en"} <= {d["language"] for d in dist["distribution"]}
    assert dist["arabizi_share"] == 0.2  # 1 of 5 comments is Arabizi


# --- top hashtags / authors (reach) -----------------------------------------------
def test_top_hashtags():
    _, post_items = _model()
    tags = {t["hashtag"]: t["count"] for t in rollups.top_hashtags(post_items, Filters())}
    assert "haircare" in tags and "vatika" in tags


def test_top_authors_ranked_by_engagement():
    items, _ = _model()
    authors = rollups.top_authors(items, Filters())
    likes = [a["total_likes"] for a in authors]
    assert likes == sorted(likes, reverse=True)
    assert authors[0]["total_likes"] == 230  # layla.skincare, highest-liked comment
    assert all("sentiment" not in a for a in authors)  # reach view, no fused sentiment


# --- post explorer = shared drill target ------------------------------------------
def test_post_explorer_drilldown_by_sentiment():
    items, _ = _model()
    rows = rollups.post_explorer(items, Filters(sentiment="negative"))
    assert len(rows) == 1
    r = rows[0]
    assert r["sentiment"] == "negative"
    assert r["url"]  # drillable to source
    assert r["text_en"]  # English display text present
    assert r["confidence"] is not None


# --- filter options ---------------------------------------------------------------
def test_filter_options():
    items, post_items = _model()
    opts = rollups.filter_options(post_items, items)
    assert opts["platforms"] == ["tiktok"]
    assert "Vatika" in opts["brands"]
    assert "UAE" in opts["markets"]
    assert opts["date_min"] and opts["date_max"]


# --- volume / reach kept separate from sentiment ----------------------------------
def test_volume_summary_is_reach_only():
    items, post_items = _model()
    vol = rollups.volume_summary(post_items, items, Filters())
    assert vol["posts"] == 1
    assert vol["comments"] == 5
    # Engagement is a separate block; there is no sentiment/net key fused in here.
    assert "net_score" not in vol
    assert set(vol["engagement"]) >= {"likes", "views", "comments_count"}


def test_rollups_never_fold_engagement_into_sentiment():
    """Rule 2, enforced on source: the sentiment-split path must not read engagement."""
    for fn in (rollups.sentiment_split, rollups.net_sentiment_trend, rollups._split):
        src = inspect.getsource(fn)
        for term in ("likes", "views", "shares", "follower", "metrics"):
            assert term not in src, f"{fn.__name__} must not touch engagement ({term})"
