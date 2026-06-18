"""Contract test: the TikTok adapter emits valid NormalizedRecords.

This is the contract EVERY platform adapter must satisfy (CLAUDE.md §2).
"""

from adapters.tiktok.adapter import TikTokAdapter
from adapters.tiktok.provider import FixtureProvider
from core.schema import CollectRequest, InputType, NormalizedRecord, Platform


def _request():
    return CollectRequest(
        input_type=InputType.post_url,
        target="https://www.tiktok.com/@vatika.mena/video/7298451200000000001",
        platform=Platform.tiktok,
    )


def test_adapter_emits_normalized_records():
    adapter = TikTokAdapter(provider=FixtureProvider())
    records = list(adapter.collect(_request()))

    assert len(records) == 1
    rec = records[0]
    assert isinstance(rec, NormalizedRecord)  # validates the schema by construction
    assert rec.platform is Platform.tiktok
    assert rec.post_id == "7298451200000000001"
    assert rec.url.startswith("https://www.tiktok.com/")
    assert len(rec.comments) == 5


def test_adapter_stamps_collected_at_and_source_method():
    """Compliance: every record must carry collection provenance (CLAUDE.md §6)."""
    adapter = TikTokAdapter(provider=FixtureProvider())
    rec = next(iter(adapter.collect(_request())))
    assert rec.collected_at  # non-empty timestamp
    assert rec.source_method.startswith("fixture:apify:")


def test_metrics_separate_from_comments():
    adapter = TikTokAdapter(provider=FixtureProvider())
    rec = next(iter(adapter.collect(_request())))
    assert rec.metrics.views == 980000
    assert rec.metrics.likes == 12400
    assert rec.metrics.comments_count == 5
