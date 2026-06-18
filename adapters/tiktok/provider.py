"""TikTok collection providers.

TikTok has no open comment API, so collection goes through a managed scraping layer
(Apify by default). Both providers implement the same `Provider` interface, so the
adapter and pipeline never know which one is in use (CLAUDE.md §2).

- FixtureProvider: replays a recorded Apify payload. Deterministic and offline — this
  is what tests run against.
- ApifyProvider: live Apify actor. Only used when APIFY_TOKEN is present in the env;
  the token is read from the environment, never from code/config/context.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from adapters.base import Provider
from core.schema import CollectRequest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "tiktok_post.json"

# The Apify actor that backs live collection. Recorded into source_method for audit.
APIFY_ACTOR = "clockworks/tiktok-scraper"


class FixtureProvider(Provider):
    """Replays a recorded scrape payload. Default in tests and no-token environments."""

    source_method = f"fixture:apify:{APIFY_ACTOR}"

    def __init__(self, fixture_path: Path = FIXTURE_PATH):
        self._fixture_path = fixture_path

    def fetch(self, request: CollectRequest) -> list[dict]:
        with open(self._fixture_path, encoding="utf-8") as fh:
            return json.load(fh)


class ApifyProvider(Provider):
    """Live Apify actor run. Requires APIFY_TOKEN in the environment."""

    source_method = f"apify:{APIFY_ACTOR}"

    def __init__(self, token: str | None = None):
        self._token = token or os.environ.get("APIFY_TOKEN")
        if not self._token:
            raise RuntimeError(
                "APIFY_TOKEN not set — live TikTok collection is unavailable. "
                "Use FixtureProvider for offline/test runs."
            )

    def fetch(self, request: CollectRequest) -> list[dict]:  # pragma: no cover - live path
        # Live actor invocation is intentionally not exercised in the slice's tests.
        # Wiring (run actor, poll dataset, page results) goes here behind the same shape
        # FixtureProvider returns, so the adapter is unchanged when this is enabled.
        raise NotImplementedError(
            "Live Apify collection is wired in a later slice; "
            "the fixture path is the supported route for now."
        )


def default_provider() -> Provider:
    """Pick the provider based on environment: live if a token exists, else fixture."""
    if os.environ.get("APIFY_TOKEN"):
        return ApifyProvider()
    return FixtureProvider()
