"""Config-as-data integrity (CLAUDE.md §6): the competitor taxonomy and seed
series must load and stay internally consistent."""

from __future__ import annotations

from growth.config import load_competitors, load_seed_snapshots
from growth.models import FollowerSnapshot, GrowthPlatform


def test_competitors_load_and_have_at_least_one_handle():
    comps = load_competitors()
    assert len(comps) > 50
    for c in comps:
        assert c.brand
        assert c.instagram_handle or c.tiktok_handle  # at least one platform


def test_seed_snapshots_are_valid_records():
    rows = load_seed_snapshots()
    assert len(rows) > 1000
    platforms = set()
    for r in rows:
        snap = FollowerSnapshot(**r)  # validates period format + non-negative count
        platforms.add(snap.platform)
    assert platforms == {GrowthPlatform.instagram, GrowthPlatform.tiktok}


def test_every_seed_handle_belongs_to_a_tracked_competitor():
    comps = load_competitors()
    ig_handles = {c.instagram_handle for c in comps if c.instagram_handle}
    tt_handles = {c.tiktok_handle for c in comps if c.tiktok_handle}
    for r in load_seed_snapshots():
        if r["platform"] == "instagram":
            assert r["handle"] in ig_handles
        else:
            assert r["handle"] in tt_handles
