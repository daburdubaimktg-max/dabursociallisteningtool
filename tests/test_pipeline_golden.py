"""Golden end-to-end pipeline test on the hand-labeled MENA fixture.

Includes the requested assertion (addition #1): the Arabic and Arabizi comments in the
fixture are detected and tagged correctly — Arabizi is NOT collapsed to English.
Also asserts Rule 1: comments are scored on original text, and text_en is display-only.
"""

from adapters.tiktok.adapter import TikTokAdapter
from adapters.tiktok.provider import FixtureProvider
from core.schema import CollectRequest, InputType, Platform, SentimentLabel
from nlp.stub import StubNLPService
from pipeline.run import run_job
from pipeline.store import Store


def _run():
    request = CollectRequest(
        input_type=InputType.post_url,
        target="https://www.tiktok.com/@vatika.mena/video/7298451200000000001",
        platform=Platform.tiktok,
    )
    store = Store(":memory:")
    adapter = TikTokAdapter(provider=FixtureProvider())
    result = run_job(request, adapter, StubNLPService(), store)
    return result, store


def test_pipeline_runs_end_to_end():
    result, _ = _run()
    assert result.posts == 1
    assert result.comments == 5


def test_arabic_and_arabizi_detected_correctly():
    """Addition #1: at least one Arabic and one Arabizi comment, tagged correctly."""
    _, store = _run()
    rows = store._conn.execute(
        "SELECT comment_id, comment_json FROM silver_comments"
    ).fetchall()
    import json

    by_id = {r[0]: json.loads(r[1]) for r in rows}

    # c_0001 is Arabic script.
    assert by_id["c_0001"]["detected_language"] == "ar"
    # c_0002 is Arabizi ("wallah 7elo ... 3ajabni") — must NOT be detected as English.
    assert by_id["c_0002"]["detected_language"] == "arabizi"
    assert by_id["c_0002"]["detected_language"] != "en"


def test_sentiment_scored_in_language_with_model_version():
    _, store = _run()
    import json

    rows = store._conn.execute("SELECT comment_json FROM silver_comments").fetchall()
    for (cj,) in rows:
        c = json.loads(cj)
        # Rule 1: scored, and text_en exists only for display (and is marked stub).
        assert c["sentiment"] is not None
        assert c["sentiment"]["model_version"] == "stub"
        assert c["text_en"].startswith("[stub-translation]")


def test_golden_sentiment_labels():
    """Snapshot the per-comment labels from the deterministic stub."""
    _, store = _run()
    import json

    rows = store._conn.execute(
        "SELECT comment_id, sentiment_label FROM silver_comments"
    ).fetchall()
    labels = {r[0]: r[1] for r in rows}
    assert labels == {
        "c_0001": "positive",  # Arabic: رائع / أحب / أنصح
        "c_0002": "positive",  # Arabizi: 7elo / 3ajabni / 🔥
        "c_0003": "negative",  # fake / terrible / leaks
        "c_0004": "positive",  # love / best
        "c_0005": "neutral",   # availability question
    }


def test_golden_net_sentiment():
    """3 positive, 1 negative, 1 neutral → (3 − 1) / 5 = 0.4."""
    result, _ = _run()
    net = result.net_sentiment
    assert (net.positive, net.neutral, net.negative, net.total) == (3, 1, 1, 5)
    assert net.net_score == 0.4
