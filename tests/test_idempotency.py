"""Idempotency (acceptance criterion #3): re-running a job updates counts and appends
new comments without creating duplicates. Dedup is on platform + native id.
"""

import json

from adapters.tiktok.adapter import TikTokAdapter
from adapters.tiktok.provider import FixtureProvider
from core.schema import CollectRequest, InputType, Platform
from nlp.stub import StubNLPService
from pipeline.run import run_job
from pipeline.store import Store

FIXTURE = "adapters/tiktok/fixtures/tiktok_post.json"


def _request():
    return CollectRequest(
        input_type=InputType.post_url,
        target="https://www.tiktok.com/@vatika.mena/video/7298451200000000001",
        platform=Platform.tiktok,
    )


def test_rerun_does_not_duplicate():
    store = Store(":memory:")
    adapter = TikTokAdapter(provider=FixtureProvider())

    r1 = run_job(_request(), adapter, StubNLPService(), store)
    r2 = run_job(_request(), adapter, StubNLPService(), store)

    # Same inputs re-run → identical counts, no duplicates.
    assert (r1.posts, r1.comments) == (1, 5)
    assert (r2.posts, r2.comments) == (1, 5)


def test_new_comment_appends_without_duplicating(tmp_path):
    store = Store(":memory:")

    # First run with the base fixture.
    run_job(_request(), TikTokAdapter(provider=FixtureProvider()), StubNLPService(), store)
    assert store.comment_count() == 5

    # Second run with an updated payload: a new comment + a changed like count on an
    # existing comment. The new one appends; the existing one updates, not duplicates.
    with open(FIXTURE, encoding="utf-8") as fh:
        payload = json.load(fh)
    payload[0]["diggCount"] = 99999  # changed engagement
    payload[0]["comments"].append(
        {
            "cid": "c_0006",
            "text": "amazing, love it",
            "uniqueId": "new_user",
            "diggCount": 7,
            "createTimeISO": "2026-06-11T08:00:00Z",
        }
    )
    updated = tmp_path / "updated.json"
    updated.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    run_job(_request(), TikTokAdapter(provider=FixtureProvider(updated)), StubNLPService(), store)

    assert store.comment_count() == 6  # 5 + 1 new, no duplicates
    assert store.post_count() == 1  # same post, updated in place
