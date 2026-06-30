"""Follower-growth KPIs (a reach dimension — CLAUDE.md §4 Volume & reach, Rule 2).

Everything here is computed from follower snapshots ONLY. There is no sentiment input:
follower growth measures reach, and reach is never blended with sentiment. Each KPI
drills down to the underlying per-brand series.

Definitions:
- MoM growth  = followers[m] − followers[m−1];  pct = delta / followers[m−1]
- Leaderboard = end_followers − start_followers over a chosen window
- Share of voice = a brand's followers ÷ total tracked followers (in a cut)
"""

from __future__ import annotations

from growth.models import GrowthPlatform, GrowthPoint, LeaderboardRow
from growth.store import GrowthStore


def _pct(delta: int, prev: int) -> float | None:
    if prev <= 0:
        return None
    return round(delta / prev, 4)


def growth_series(store: GrowthStore, platform: GrowthPlatform) -> dict[str, list[GrowthPoint]]:
    """{brand: [GrowthPoint per period]} with MoM delta and pct_change."""
    meta = {(s.brand): (s.category, s.region) for s in store.snapshots(platform)}
    out: dict[str, list[GrowthPoint]] = {}
    for brand, series in store.series_by_brand(platform).items():
        cat, region = meta.get(brand, (None, None))
        points: list[GrowthPoint] = []
        prev: int | None = None
        for period in sorted(series):
            followers = series[period]
            delta = followers - prev if prev is not None else None
            points.append(
                GrowthPoint(
                    platform=platform,
                    brand=brand,
                    category=cat,
                    region=region,
                    period=period,
                    followers=followers,
                    prev_followers=prev,
                    delta=delta,
                    pct_change=_pct(delta, prev) if (delta is not None and prev) else None,
                )
            )
            prev = followers
        out[brand] = points
    return out


def leaderboard(
    store: GrowthStore,
    platform: GrowthPlatform,
    start_period: str | None = None,
    end_period: str | None = None,
) -> list[LeaderboardRow]:
    """Brands ranked by absolute follower gain over [start_period, end_period].

    Window defaults to the first and last periods present for the platform. A brand is
    included only if it has a reading at or after `start_period` and at `end_period`'s
    side; the nearest available period within the window is used at each end.
    """
    periods = store.periods(platform)
    if not periods:
        return []
    start_period = start_period or periods[0]
    end_period = end_period or periods[-1]

    rows: list[LeaderboardRow] = []
    meta = {s.brand: (s.category, s.region) for s in store.snapshots(platform)}
    for brand, series in store.series_by_brand(platform).items():
        in_window = {p: v for p, v in series.items() if start_period <= p <= end_period}
        if len(in_window) < 1:
            continue
        ordered = sorted(in_window)
        sp, ep = ordered[0], ordered[-1]
        if sp == ep:
            continue  # need two distinct readings to show growth
        sv, ev = in_window[sp], in_window[ep]
        cat, region = meta.get(brand, (None, None))
        rows.append(
            LeaderboardRow(
                brand=brand,
                platform=platform,
                category=cat,
                region=region,
                start_period=sp,
                end_period=ep,
                start_followers=sv,
                end_followers=ev,
                delta=ev - sv,
                pct_change=_pct(ev - sv, sv),
            )
        )
    rows.sort(key=lambda r: r.delta, reverse=True)
    return rows


def share_of_voice(
    store: GrowthStore, platform: GrowthPlatform, period: str | None = None
) -> list[dict]:
    """Each brand's share of total tracked followers for a period (reach SoV).

    Returns rows sorted by share desc: {brand, followers, share}. `share` in [0, 1].
    """
    periods = store.periods(platform)
    if not periods:
        return []
    period = period or periods[-1]
    latest: dict[str, int] = {}
    for brand, series in store.series_by_brand(platform).items():
        # nearest reading at or before the chosen period
        avail = [p for p in series if p <= period]
        if avail:
            latest[brand] = series[max(avail)]
    total = sum(latest.values())
    rows = [
        {
            "brand": b,
            "followers": v,
            "share": round(v / total, 4) if total else 0.0,
        }
        for b, v in latest.items()
    ]
    rows.sort(key=lambda r: r["followers"], reverse=True)
    return rows


def combined_latest(store: GrowthStore, period: str | None = None) -> list[dict]:
    """Per-brand IG + TikTok latest followers side by side (never summed into one
    blended 'social score' — IG and TikTok are reported as separate columns).

    Returns {brand, instagram, tiktok, total} sorted by total desc. `total` is the
    plain sum of two reach counts (audience size), which is legitimate; it is NOT a
    blend of different signal *types* (Rule 2 concerns mixing reach with sentiment).
    """

    def latest_map(platform: GrowthPlatform) -> dict[str, int]:
        m: dict[str, int] = {}
        for brand, series in store.series_by_brand(platform).items():
            avail = [p for p in series if period is None or p <= period]
            if avail:
                m[brand] = series[max(avail)]
        return m

    ig = latest_map(GrowthPlatform.instagram)
    tt = latest_map(GrowthPlatform.tiktok)
    brands = sorted(set(ig) | set(tt))
    rows = [
        {
            "brand": b,
            "instagram": ig.get(b),
            "tiktok": tt.get(b),
            "total": (ig.get(b) or 0) + (tt.get(b) or 0),
        }
        for b in brands
    ]
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows
