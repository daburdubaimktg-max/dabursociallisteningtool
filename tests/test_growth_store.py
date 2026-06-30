"""Idempotency + read contract for the follower store (CLAUDE.md §1)."""

from __future__ import annotations

from growth.models import FollowerSnapshot, GrowthPlatform
from growth.store import GrowthStore


def _snap(period: str, count: int, brand="Vatika", handle="vatika.arabia") -> FollowerSnapshot:
    return FollowerSnapshot(
        platform=GrowthPlatform.instagram,
        handle=handle,
        brand=brand,
        category="Hair Care",
        region="Arabia",
        period=period,
        follower_count=count,
        source_method="test",
    )


def test_recollecting_a_period_updates_not_duplicates():
    store = GrowthStore()
    store.write_silver(_snap("2026-01", 100))
    store.write_silver(_snap("2026-01", 150))  # same platform+handle+period
    assert store.snapshot_count() == 1
    series = store.series_by_brand(GrowthPlatform.instagram)
    assert series["Vatika"]["2026-01"] == 150  # updated in place


def test_distinct_periods_accumulate():
    store = GrowthStore()
    store.write_silver(_snap("2026-01", 100))
    store.write_silver(_snap("2026-02", 120))
    assert store.snapshot_count() == 2
    assert store.periods(GrowthPlatform.instagram) == ["2026-01", "2026-02"]


def test_series_sums_multiple_handles_for_same_brand_and_period():
    store = GrowthStore()
    store.write_silver(_snap("2026-01", 100, handle="vatika.arabia"))
    store.write_silver(_snap("2026-01", 30, handle="vatika.egypt"))
    series = store.series_by_brand(GrowthPlatform.instagram)
    assert series["Vatika"]["2026-01"] == 130


def test_platform_isolation():
    store = GrowthStore()
    store.write_silver(_snap("2026-01", 100))
    assert store.periods(GrowthPlatform.tiktok) == []
    assert store.series_by_brand(GrowthPlatform.tiktok) == {}
