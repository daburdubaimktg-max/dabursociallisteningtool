"""Tidy long-format export of follower snapshots, for notebooks/Streamlit/pandas.

Kept dependency-free (returns plain dicts) so the core never imports pandas. The
Streamlit app turns these rows into a DataFrame. Reach only — no sentiment.
"""

from __future__ import annotations

from growth.models import GrowthPlatform
from growth.store import GrowthStore


def long_rows(store: GrowthStore) -> list[dict]:
    """One row per (platform, brand, handle, period) follower reading.

    Columns: platform, brand, handle, category, region, period, followers.
    """
    rows: list[dict] = []
    for platform in (GrowthPlatform.instagram, GrowthPlatform.tiktok):
        for s in store.snapshots(platform):
            rows.append(
                {
                    "platform": s.platform.value,
                    "brand": s.brand,
                    "handle": s.handle,
                    "category": s.category or "Unspecified",
                    "region": s.region or "Unspecified",
                    "period": s.period,
                    "followers": s.follower_count,
                }
            )
    return rows
