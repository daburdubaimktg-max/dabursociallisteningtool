"""Follower adapter: turns competitor handles + a provider reading into normalized
`FollowerSnapshot` records, stamping provenance (collected_at, source_method) on each.

One adapter handles both platforms because the normalized output is identical; the
platform-specific bit is entirely inside the provider (which actor, which field).
"""

from __future__ import annotations

from datetime import datetime, timezone

from adapters.profile.provider import FollowerProvider, SeedFollowerProvider
from growth.models import Competitor, FollowerSnapshot, GrowthPlatform


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FollowerAdapter:
    def __init__(self, provider: FollowerProvider | None = None):
        self._provider = provider or SeedFollowerProvider()

    def collect(
        self,
        competitors: list[Competitor],
        platform: GrowthPlatform,
        period: str,
    ) -> list[FollowerSnapshot]:
        """Collect one follower snapshot per competitor that has a handle on `platform`
        and a resolvable count. Brands without a handle or without a reading are skipped,
        never errored on (CLAUDE.md §2)."""
        by_handle: dict[str, Competitor] = {}
        for c in competitors:
            h = c.handle_for(platform)
            if h:
                by_handle[h] = c

        counts = self._provider.fetch(platform, list(by_handle))
        collected_at = _utcnow_iso()
        source_method = getattr(self._provider, "source_method", "profile:unknown")

        snapshots: list[FollowerSnapshot] = []
        for handle, count in counts.items():
            c = by_handle[handle]
            try:
                snapshots.append(
                    FollowerSnapshot(
                        platform=platform,
                        handle=handle,
                        brand=c.brand,
                        category=c.category,
                        region=c.region,
                        period=period,
                        follower_count=count,
                        collected_at=collected_at,
                        source_method=source_method,
                    )
                )
            except Exception:  # noqa: BLE001 - resilience: skip one bad reading
                continue
        return snapshots
