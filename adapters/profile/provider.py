"""Follower-count collection providers.

Like the post providers (CLAUDE.md §2), the live source is abstracted behind a
common interface so it can be swapped (Apify → Bright Data → official Graph/TikTok
API) without touching the adapter or pipeline.

- SeedFollowerProvider: replays the recorded historical monthly series mirrored from
  the source tracker (config/seed_followers.json). Deterministic, offline — this is
  what tests and no-token environments run against, and it is what makes the dashboard
  render with real history out of the box.
- ApifyFollowerProvider: live profile scrape. Only used when APIFY_TOKEN is in the
  env; the token is read from the environment, never from code/config/context.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from growth.config import load_seed_snapshots
from growth.models import GrowthPlatform

# Apify actors that back live profile collection, recorded into source_method for audit.
APIFY_ACTORS = {
    GrowthPlatform.instagram: "apify/instagram-profile-scraper",
    GrowthPlatform.tiktok: "clockworks/tiktok-profile-scraper",
}


class FollowerProvider(ABC):
    """Returns follower counts keyed by handle for a platform."""

    source_method: str

    @abstractmethod
    def fetch(self, platform: GrowthPlatform, handles: list[str]) -> dict[str, int]:
        """Return {handle: follower_count} for the handles this provider can resolve.

        Missing handles are simply absent from the result (never block on one bad
        handle — CLAUDE.md §2). Counts are the *current* reading for the period.
        """


class SeedFollowerProvider(FollowerProvider):
    """Replays the historical monthly series. The default in tests and no-token envs.

    For a requested `period`, returns each handle's recorded count for that month.
    With no period it returns each handle's latest recorded count.
    """

    source_method = "fixture:seed:master_social_tracker"

    def __init__(self, period: str | None = None, rows: list[dict] | None = None):
        self._period = period
        self._rows = rows if rows is not None else load_seed_snapshots()

    def fetch(self, platform: GrowthPlatform, handles: list[str]) -> dict[str, int]:
        wanted = set(handles)
        # latest count per handle, or the count for the requested period
        best: dict[str, tuple[str, int]] = {}
        for r in self._rows:
            if r["platform"] != platform.value or r["handle"] not in wanted:
                continue
            if self._period is not None and r["period"] != self._period:
                continue
            cur = best.get(r["handle"])
            if cur is None or r["period"] > cur[0]:
                best[r["handle"]] = (r["period"], int(r["follower_count"]))
        return {h: v[1] for h, v in best.items()}


class ApifyFollowerProvider(FollowerProvider):
    """Live profile scrape via Apify. Requires APIFY_TOKEN in the environment."""

    def __init__(self, platform: GrowthPlatform, token: str | None = None):
        self._token = token or os.environ.get("APIFY_TOKEN")
        if not self._token:
            raise RuntimeError(
                "APIFY_TOKEN not set — live follower collection is unavailable. "
                "Use SeedFollowerProvider for offline/test runs."
            )
        self.source_method = f"apify:{APIFY_ACTORS[platform]}"

    def fetch(  # pragma: no cover - live path
        self, platform: GrowthPlatform, handles: list[str]
    ) -> dict[str, int]:
        # Wiring (run profile actor, poll dataset, read followersCount) goes here behind
        # the same {handle: count} shape SeedFollowerProvider returns, so the adapter is
        # unchanged when this is enabled.
        raise NotImplementedError(
            "Live Apify profile collection is wired in a later slice; "
            "the seed/fixture path is the supported route for now."
        )


def default_follower_provider(period: str | None = None) -> FollowerProvider:
    """Live if a token exists, else the deterministic seed provider.

    Note: live providers are platform-scoped, so when a token is present this returns a
    seed provider still — live wiring is constructed per-platform in the adapter once the
    actor integration lands. Kept simple for the slice.
    """
    return SeedFollowerProvider(period=period)
