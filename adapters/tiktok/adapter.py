"""TikTok adapter: normalizes raw Apify payloads to the shared schema."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from adapters.base import Adapter, Provider
from adapters.tiktok.provider import FixtureProvider
from core.schema import (
    Comment,
    MediaType,
    Metrics,
    NormalizedRecord,
    Platform,
)
from pipeline.text_utils import extract_emojis, extract_hashtags


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TikTokAdapter(Adapter):
    def __init__(self, provider: Provider | None = None):
        self._provider = provider or FixtureProvider()

    def raw_payloads(self, request) -> list[dict]:
        return self._provider.fetch(request)

    def collect(self, request) -> Iterable[NormalizedRecord]:
        source_method = getattr(self._provider, "source_method", "tiktok:unknown")
        for raw in self.raw_payloads(request):
            try:
                yield self._normalize(raw, source_method)
            except Exception:  # noqa: BLE001 - resilience: never block on one bad post
                # A real impl records partial-failure state here; for the slice we skip.
                continue

    def _normalize(self, raw: dict, source_method: str) -> NormalizedRecord:
        collected_at = _utcnow_iso()
        author = raw.get("authorMeta") or {}
        caption = raw.get("text") or ""

        comments = [
            Comment(
                comment_id=str(c["cid"]),
                author=c.get("uniqueId"),
                text_raw=c.get("text") or "",
                likes=c.get("diggCount"),
                replied_to=c.get("replyToId"),
                posted_at=c.get("createTimeISO"),
            )
            for c in (raw.get("comments") or [])
        ]

        return NormalizedRecord(
            post_id=str(raw["id"]),
            platform=Platform.tiktok,
            author_handle=author.get("name"),
            author_id=author.get("id"),
            author_follower_count=author.get("fans"),
            url=raw.get("webVideoUrl") or "",
            posted_at=raw.get("createTimeISO"),
            collected_at=collected_at,
            source_method=source_method,
            caption_or_title=caption,
            media_type=MediaType.video,
            metrics=Metrics(
                likes=raw.get("diggCount"),
                comments_count=raw.get("commentCount"),
                views=raw.get("playCount"),
                shares=raw.get("shareCount"),
                saves=raw.get("collectCount"),
            ),
            comments=comments,
            hashtags=extract_hashtags(caption),
            emojis=extract_emojis(caption),
        )
