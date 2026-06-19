"""Instagram adapter: contract validity, in-language detection, and idempotency.

Mirrors the TikTok adapter's guarantees (CLAUDE.md §2):
  - emits valid NormalizedRecords,
  - the pipeline tags Arabic + Arabizi comments to the Arabic path (Rule 1),
  - re-running a job updates counts and appends new comments without duplicating.
"""

import json

from adapters.instagram.adapter import InstagramAdapter
from adapters.instagram.provider import FixtureProvider
from core.schema import CollectRequest, InputType, MediaType, NormalizedRecord, Platform
from nlp.stub import StubNLPService
from pipeline.run import run_job
from pipeline.store import Store

FIXTURE = "adapters/instagram/fixtures/instagram_post.json"


def _request():
    return CollectRequest(
        input_type=InputType.post_url,
        target="https://www.instagram.com/p/C8xVatikaAML/",
        platform=Platform.instagram,
    )


# --- contract: valid NormalizedRecords --------------------------------------------
def test_adapter_emits_normalized_records():
    adapter = InstagramAdapter(provider=FixtureProvider())
    records = list(adapter.collect(_request()))

    assert len(records) == 1
    rec = records[0]
    assert isinstance(rec, NormalizedRecord)  # validates the schema by construction
    assert rec.platform is Platform.instagram
    assert rec.post_id == "3201145600000000002"
    assert rec.url.startswith("https://www.instagram.com/")
    assert rec.media_type is MediaType.video
    assert len(rec.comments) == 5


def test_adapter_stamps_collected_at_and_source_method():
    """Compliance: every record must carry collection provenance (CLAUDE.md §6)."""
    adapter = InstagramAdapter(provider=FixtureProvider())
    rec = next(iter(adapter.collect(_request())))
    assert rec.collected_at  # non-empty timestamp
    assert rec.source_method.startswith("fixture:apify:")


def test_metrics_separate_from_comments():
    """Reach ≠ sentiment: engagement lives on metrics, never fused (Rule 2)."""
    adapter = InstagramAdapter(provider=FixtureProvider())
    rec = next(iter(adapter.collect(_request())))
    assert rec.metrics.likes == 8800
    assert rec.metrics.comments_count == 5
    assert rec.metrics.views == 415000
    # IG exposes neither shares nor saves publicly.
    assert rec.metrics.shares is None
    assert rec.metrics.saves is None


# --- in-language detection on the fixture comments (Rule 1) ------------------------
def _comments_by_id():
    adapter = InstagramAdapter(provider=FixtureProvider())
    rec = next(iter(adapter.collect(_request())))
    return {c.comment_id: c for c in rec.comments}


def test_detect_tags_arabic_comment():
    nlp = StubNLPService()
    comments = _comments_by_id()
    arabic = comments["ig_c_0001"]  # "منتج رائع جدا ..."
    assert nlp.detect(arabic.text_raw).language == "ar"


def test_detect_tags_arabizi_comment_not_english():
    # Latin-script Arabic must route to the Arabic path, never be called English (Rule 1).
    nlp = StubNLPService()
    comments = _comments_by_id()
    arabizi = comments["ig_c_0002"]  # "wallah el rou7a 7elwa ktir ..."
    assert nlp.detect(arabizi.text_raw).language == "arabizi"


def test_fixture_contains_arabic_and_arabizi():
    """Guard the fixture itself so the detection assertions stay meaningful."""
    comments = _comments_by_id()
    nlp = StubNLPService()
    langs = {cid: nlp.detect(c.text_raw).language for cid, c in comments.items()}
    assert "ar" in langs.values()
    assert "arabizi" in langs.values()


# --- idempotency (acceptance criterion #3) ----------------------------------------
def test_rerun_does_not_duplicate():
    store = Store(":memory:")
    adapter = InstagramAdapter(provider=FixtureProvider())

    r1 = run_job(_request(), adapter, StubNLPService(), store)
    r2 = run_job(_request(), adapter, StubNLPService(), store)

    assert (r1.posts, r1.comments) == (1, 5)
    assert (r2.posts, r2.comments) == (1, 5)  # same inputs → no duplicates


def test_new_comment_appends_without_duplicating(tmp_path):
    store = Store(":memory:")

    run_job(_request(), InstagramAdapter(provider=FixtureProvider()), StubNLPService(), store)
    assert store.comment_count() == 5

    # Re-collect with an updated payload: a new comment + changed engagement on the post.
    # The new comment appends; the post updates in place — no duplicates (dedup on
    # platform + native id).
    with open(FIXTURE, encoding="utf-8") as fh:
        payload = json.load(fh)
    payload[0]["likesCount"] = 99999
    payload[0]["latestComments"].append(
        {
            "id": "ig_c_0006",
            "text": "amazing, love it",
            "ownerUsername": "new_user",
            "likesCount": 4,
            "timestamp": "2026-06-13T08:00:00Z",
        }
    )
    updated = tmp_path / "updated.json"
    updated.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    run_job(
        _request(),
        InstagramAdapter(provider=FixtureProvider(updated)),
        StubNLPService(),
        store,
    )

    assert store.comment_count() == 6  # 5 + 1 new, no duplicates
    assert store.post_count() == 1  # same post, updated in place
