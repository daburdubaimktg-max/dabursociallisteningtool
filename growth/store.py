"""Follower-snapshot persistence (bronze → silver), mirroring pipeline/store.py.

SQLite for the slice. Idempotency is an acceptance criterion (CLAUDE.md §1):
silver is keyed on (platform, handle, period), so re-collecting a month UPSERTs the
count rather than duplicating the row. The historical seed and a fresh live reading
land in the same table the same way.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from growth.models import FollowerSnapshot, GrowthPlatform

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bronze_followers (
    platform TEXT NOT NULL,
    handle   TEXT NOT NULL,
    period   TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    collected_at TEXT,
    PRIMARY KEY (platform, handle, period)
);
CREATE TABLE IF NOT EXISTS silver_followers (
    platform TEXT NOT NULL,
    handle   TEXT NOT NULL,
    period   TEXT NOT NULL,
    brand    TEXT NOT NULL,
    category TEXT,
    region   TEXT,
    follower_count INTEGER NOT NULL,
    collected_at   TEXT,
    source_method  TEXT,
    PRIMARY KEY (platform, handle, period)
);
"""


class GrowthStore:
    def __init__(self, db_path: str | Path = ":memory:"):
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- writes -----------------------------------------------------------------
    def write_bronze(self, snap: FollowerSnapshot, raw: dict) -> None:
        self._conn.execute(
            "INSERT INTO bronze_followers (platform, handle, period, raw_json, collected_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(platform, handle, period) DO UPDATE SET "
            "raw_json=excluded.raw_json, collected_at=excluded.collected_at",
            (
                snap.platform.value,
                snap.handle,
                snap.period,
                json.dumps(raw, ensure_ascii=False),
                snap.collected_at,
            ),
        )
        self._conn.commit()

    def write_silver(self, snap: FollowerSnapshot) -> None:
        self._conn.execute(
            "INSERT INTO silver_followers "
            "(platform, handle, period, brand, category, region, follower_count, "
            " collected_at, source_method) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(platform, handle, period) DO UPDATE SET "
            "brand=excluded.brand, category=excluded.category, region=excluded.region, "
            "follower_count=excluded.follower_count, collected_at=excluded.collected_at, "
            "source_method=excluded.source_method",
            (
                snap.platform.value,
                snap.handle,
                snap.period,
                snap.brand,
                snap.category,
                snap.region,
                snap.follower_count,
                snap.collected_at,
                snap.source_method,
            ),
        )
        self._conn.commit()

    def write_snapshots(self, snaps: list[FollowerSnapshot]) -> int:
        for s in snaps:
            self.write_silver(s)
        return len(snaps)

    # --- reads ------------------------------------------------------------------
    def snapshot_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM silver_followers").fetchone()[0]

    def periods(self, platform: GrowthPlatform | None = None) -> list[str]:
        if platform is None:
            rows = self._conn.execute(
                "SELECT DISTINCT period FROM silver_followers ORDER BY period"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT DISTINCT period FROM silver_followers WHERE platform=? ORDER BY period",
                (platform.value,),
            ).fetchall()
        return [r[0] for r in rows]

    def snapshots(self, platform: GrowthPlatform | None = None) -> list[FollowerSnapshot]:
        sql = (
            "SELECT platform, handle, period, brand, category, region, follower_count, "
            "collected_at, source_method FROM silver_followers"
        )
        params: tuple = ()
        if platform is not None:
            sql += " WHERE platform=?"
            params = (platform.value,)
        sql += " ORDER BY brand, handle, period"
        rows = self._conn.execute(sql, params).fetchall()
        return [
            FollowerSnapshot(
                platform=GrowthPlatform(r["platform"]),
                handle=r["handle"],
                period=r["period"],
                brand=r["brand"],
                category=r["category"],
                region=r["region"],
                follower_count=r["follower_count"],
                collected_at=r["collected_at"],
                source_method=r["source_method"],
            )
            for r in rows
        ]

    def series_by_brand(self, platform: GrowthPlatform) -> dict[str, dict[str, int]]:
        """{brand: {period: follower_count}} for one platform.

        When a brand has multiple handles in a region split, counts for the same period
        are summed — this matches how the source tracker rolls a brand up across its
        regional handles.
        """
        out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for s in self.snapshots(platform):
            out[s.brand][s.period] += s.follower_count
        return {b: dict(p) for b, p in out.items()}
