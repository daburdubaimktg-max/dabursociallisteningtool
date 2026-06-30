"""Load the competitor taxonomy — config-as-data, editable without a redeploy
(CLAUDE.md §6). The brand → handle → category → region mapping lives in
`config/competitors.json`, not in code.
"""

from __future__ import annotations

import json
from pathlib import Path

from growth.models import Competitor

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
COMPETITORS_PATH = CONFIG_DIR / "competitors.json"
SEED_PATH = CONFIG_DIR / "seed_followers.json"


def load_competitors(path: Path = COMPETITORS_PATH) -> list[Competitor]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return [Competitor(**row) for row in raw]


def load_seed_snapshots(path: Path = SEED_PATH) -> list[dict]:
    """Raw seed rows (historical monthly follower series mirrored from the source
    tracker). Returned as dicts so the adapter/pipeline stamps provenance on them."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
