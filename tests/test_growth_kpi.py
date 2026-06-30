"""Growth KPI math + the reach≠sentiment guarantee (CLAUDE.md Rule 2)."""

from __future__ import annotations

import inspect

import kpi.growth as growth_kpi
from growth.models import FollowerSnapshot, GrowthPlatform
from growth.store import GrowthStore
from kpi.growth import combined_latest, growth_series, leaderboard, share_of_voice


def _store() -> GrowthStore:
    store = GrowthStore()
    rows = [
        ("instagram", "vatika.arabia", "Vatika", "2026-01", 100),
        ("instagram", "vatika.arabia", "Vatika", "2026-02", 150),
        ("instagram", "vatika.arabia", "Vatika", "2026-03", 120),
        ("instagram", "garnierarabia", "Garnier", "2026-01", 1000),
        ("instagram", "garnierarabia", "Garnier", "2026-03", 1100),
        ("tiktok", "vatika.arabia", "Vatika", "2026-01", 50),
        ("tiktok", "vatika.arabia", "Vatika", "2026-03", 90),
    ]
    for plat, handle, brand, period, count in rows:
        store.write_silver(
            FollowerSnapshot(
                platform=GrowthPlatform(plat),
                handle=handle,
                brand=brand,
                category="Hair Care",
                region="Arabia",
                period=period,
                follower_count=count,
                source_method="test",
            )
        )
    return store


def test_mom_growth_delta_and_pct():
    points = growth_series(_store(), GrowthPlatform.instagram)["Vatika"]
    assert [p.followers for p in points] == [100, 150, 120]
    assert points[0].delta is None and points[0].pct_change is None
    assert points[1].delta == 50 and points[1].pct_change == 0.5
    assert points[2].delta == -30 and points[2].pct_change == -0.2


def test_leaderboard_ranks_by_absolute_gain():
    rows = leaderboard(_store(), GrowthPlatform.instagram)
    # Garnier +100 (1000→1100) outranks Vatika +20 (100→120)
    assert [r.brand for r in rows] == ["Garnier", "Vatika"]
    assert rows[0].delta == 100
    assert rows[1].start_followers == 100 and rows[1].end_followers == 120


def test_share_of_voice_sums_to_one():
    rows = share_of_voice(_store(), GrowthPlatform.instagram, period="2026-03")
    assert abs(sum(r["share"] for r in rows) - 1.0) < 1e-6
    # Garnier (1100) dominates over Vatika (120)
    assert rows[0]["brand"] == "Garnier"


def test_combined_keeps_platforms_separate():
    rows = {r["brand"]: r for r in combined_latest(_store())}
    v = rows["Vatika"]
    assert v["instagram"] == 120 and v["tiktok"] == 90  # distinct columns
    assert v["total"] == 210


def test_growth_kpis_take_no_sentiment_argument():
    # Rule 2: reach KPIs must not accept any sentiment signal.
    for fn in (growth_series, leaderboard, share_of_voice, combined_latest):
        params = set(inspect.signature(fn).parameters)
        assert not (params & {"sentiment", "label", "score", "labels"})
    # module imports nothing from the sentiment KPI either
    src = inspect.getsource(growth_kpi)
    assert "net_sentiment" not in src and "SentimentLabel" not in src
