"""Instagram adapter: normalizes raw Apify payloads to the shared schema (CLAUDE.md §1).

Same pattern as the TikTok adapter — only the field mapping differs. The pipeline
downstream is unchanged: it consumes NormalizedRecords regardless of platform.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from adapters.base import Adapter, Provider
from adapters.instagram.provider import FixtureProvider
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


# Apify instagram-scraper "type" → our media taxonomy.
_MEDIA_TYPES = {
    "Video": MediaType.video,
    "Image": MediaType.image,
    "Sidecar": MediaType.image,  # carousel — treat as image for the slice
}


class InstagramAdapter(Adapter):
    def __init__(self, provider: Provider | None = None):
        self._provider = provider or FixtureProvider()

    def raw_payloads(self, request) -> list[dict]:
        return self._provider.fetch(request)

    def collect(self, request) -> Iterable[NormalizedRecord]:
        source_method = getattr(self._provider, "source_method", "instagram:unknown")
        for raw in self.raw_payloads(request):
            try:
                yield self._normalize(raw, source_method)
            except Exception:  # noqa: BLE001 - resilience: never block on one bad post
                # A real impl records partial-failure state here; for the slice we skip.
                continue

    def _normalize(self, raw: dict, source_method: str) -> NormalizedRecord:
        collected_at = _utcnow_iso()
        caption = raw.get("caption") or ""

        comments = [
            Comment(
                comment_id=str(c["id"]),
                author=c.get("ownerUsername"),
                text_raw=c.get("text") or "",
                likes=c.get("likesCount"),
                replied_to=c.get("repliedToCommentId"),
                posted_at=c.get("timestamp"),
            )
            for c in (raw.get("latestComments") or [])
        ]

        return NormalizedRecord(
            post_id=str(raw["id"]),
            platform=Platform.instagram,
            author_handle=raw.get("ownerUsername"),
            author_id=raw.get("ownerId"),
            author_follower_count=raw.get("ownerFollowersCount"),
            url=raw.get("url") or "",
            posted_at=raw.get("timestamp"),
            collected_at=collected_at,
            source_method=source_method,
            caption_or_title=caption,
            media_type=_MEDIA_TYPES.get(raw.get("type"), MediaType.image),
            metrics=Metrics(
                likes=raw.get("likesCount"),
                comments_count=raw.get("commentsCount"),
                # IG exposes view counts on video only; no shares/saves in public data.
                views=raw.get("videoViewCount") or raw.get("videoPlayCount"),
                shares=None,
                saves=None,
            ),
            comments=comments,
            hashtags=extract_hashtags(caption),
            emojis=extract_emojis(caption),
        )
