"""Bronze → silver → gold persistence (CLAUDE.md §1).

SQLite for the slice (zero infra, runs anywhere). The interface is deliberately thin so
PostgreSQL + object storage swap in later without touching the pipeline.

Idempotency (acceptance criterion): all writes UPSERT on the dedup key
(platform + native id). Re-running a job updates counts and appends new comments
without creating duplicates.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.schema import NormalizedRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bronze (
    platform TEXT NOT NULL,
    post_id  TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    PRIMARY KEY (platform, post_id)
);
CREATE TABLE IF NOT EXISTS silver_posts (
    platform TEXT NOT NULL,
    post_id  TEXT NOT NULL,
    record_json TEXT NOT NULL,
    PRIMARY KEY (platform, post_id)
);
CREATE TABLE IF NOT EXISTS silver_comments (
    platform   TEXT NOT NULL,
    post_id    TEXT NOT NULL,
    comment_id TEXT NOT NULL,
    sentiment_label TEXT,
    comment_json TEXT NOT NULL,
    PRIMARY KEY (platform, comment_id)
);
"""


class Store:
    def __init__(self, db_path: str | Path = ":memory:"):
        # check_same_thread=False: FastAPI serves handlers from a threadpool. Safe for
        # the single-process slice; Postgres replaces this for concurrent production use.
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- bronze -----------------------------------------------------------------
    def write_bronze(self, platform: str, post_id: str, raw: dict, collected_at: str) -> None:
        self._conn.execute(
            "INSERT INTO bronze (platform, post_id, raw_json, collected_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(platform, post_id) DO UPDATE SET "
            "raw_json=excluded.raw_json, collected_at=excluded.collected_at",
            (platform, post_id, json.dumps(raw, ensure_ascii=False), collected_at),
        )
        self._conn.commit()

    # --- silver -----------------------------------------------------------------
    def write_silver(self, record: NormalizedRecord) -> None:
        self._conn.execute(
            "INSERT INTO silver_posts (platform, post_id, record_json) VALUES (?, ?, ?) "
            "ON CONFLICT(platform, post_id) DO UPDATE SET record_json=excluded.record_json",
            (record.platform.value, record.post_id, record.model_dump_json()),
        )
        for c in record.comments:
            label = c.sentiment.label.value if c.sentiment else None
            self._conn.execute(
                "INSERT INTO silver_comments "
                "(platform, post_id, comment_id, sentiment_label, comment_json) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(platform, comment_id) DO UPDATE SET "
                "sentiment_label=excluded.sentiment_label, comment_json=excluded.comment_json",
                (
                    record.platform.value,
                    record.post_id,
                    c.comment_id,
                    label,
                    c.model_dump_json(),
                ),
            )
        self._conn.commit()

    # --- reads ------------------------------------------------------------------
    def comment_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM silver_comments").fetchone()[0]

    def post_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM silver_posts").fetchone()[0]

    def comment_sentiment_labels(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT sentiment_label FROM silver_comments WHERE sentiment_label IS NOT NULL"
        ).fetchall()
        return [r[0] for r in rows]
