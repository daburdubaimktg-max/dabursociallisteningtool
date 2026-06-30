"""Build the live competitor social-growth Excel dashboard.

    python -m scripts.build_dashboard [output.xlsx] [--period YYYY-MM]

Seeds the historical follower series, optionally collects a fresh reading for a
period (fixture/seed by default; live Apify when APIFY_TOKEN is set), then writes the
multi-sheet workbook. Re-running is idempotent.
"""

from __future__ import annotations

import argparse

from dashboard_export.excel import write_dashboard
from growth.pipeline import collect_period, seed_history
from growth.store import GrowthStore


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the competitor social-growth dashboard")
    ap.add_argument("output", nargs="?", default="competitor_growth_dashboard.xlsx")
    ap.add_argument("--period", help="also collect a fresh reading for YYYY-MM")
    ap.add_argument("--db", default=":memory:", help="SQLite path (default: in-memory)")
    args = ap.parse_args()

    store = GrowthStore(args.db)
    n = seed_history(store)
    print(f"Seeded {n} historical follower snapshots.")
    if args.period:
        written = collect_period(store, args.period)
        print(f"Collected period {args.period}: {written}")
    out = write_dashboard(store, args.output)
    print(f"Wrote dashboard → {out.resolve()}  ({store.snapshot_count()} snapshots)")


if __name__ == "__main__":
    main()
