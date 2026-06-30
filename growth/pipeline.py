"""Growth pipeline: seed history, then collect the current period.

    seed (history) ─┐
                     ├─► silver_followers (idempotent) ─► gold rollups / Excel
    collect (live) ─┘

Both paths write the same idempotent silver table, so a fresh monthly reading simply
appends a new period column to the dashboard. Re-running either is safe.
"""

from __future__ import annotations

from datetime import datetime, timezone

from adapters.profile.adapter import FollowerAdapter
from adapters.profile.provider import FollowerProvider, SeedFollowerProvider
from growth.config import load_competitors, load_seed_snapshots
from growth.models import Competitor, FollowerSnapshot, GrowthPlatform
from growth.store import GrowthStore


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_history(store: GrowthStore, rows: list[dict] | None = None) -> int:
    """Load the recorded historical monthly series into bronze + silver.

    Idempotent: loading twice updates in place (dedup on platform+handle+period)."""
    rows = rows if rows is not None else load_seed_snapshots()
    collected_at = _utcnow_iso()
    count = 0
    for r in rows:
        snap = FollowerSnapshot(
            platform=GrowthPlatform(r["platform"]),
            handle=r["handle"],
            brand=r["brand"],
            category=r.get("category"),
            region=r.get("region"),
            period=r["period"],
            follower_count=int(r["follower_count"]),
            collected_at=collected_at,
            source_method="seed:master_social_tracker",
        )
        store.write_bronze(snap, raw=r)
        store.write_silver(snap)
        count += 1
    return count


def collect_period(
    store: GrowthStore,
    period: str,
    platforms: list[GrowthPlatform] | None = None,
    competitors: list[Competitor] | None = None,
    provider: FollowerProvider | None = None,
) -> dict[str, int]:
    """Collect a follower snapshot for every tracked competitor for `period`.

    Returns {platform: snapshots_written}. The provider abstracts live vs. fixture
    (CLAUDE.md §2); default is the deterministic seed provider scoped to `period`."""
    competitors = competitors if competitors is not None else load_competitors()
    platforms = platforms or [GrowthPlatform.instagram, GrowthPlatform.tiktok]
    provider = provider or SeedFollowerProvider(period=period)
    adapter = FollowerAdapter(provider=provider)

    written: dict[str, int] = {}
    for platform in platforms:
        snaps = adapter.collect(competitors, platform, period)
        for s in snaps:
            store.write_bronze(s, raw=s.model_dump(mode="json"))
        store.write_snapshots(snaps)
        written[platform.value] = len(snaps)
    return written
