"""Instagram collection providers.

Instagram has no open public comment API, so collection goes through Apify — the same
managed scraping layer used for TikTok. Both providers implement the shared `Provider`
interface, so the adapter and pipeline never know which one is in use (CLAUDE.md §2).

- FixtureProvider: replays a recorded Apify payload. Deterministic and offline — this is
  what tests/CI run against.
- ApifyProvider: live Apify actor run. Only used when APIFY_TOKEN is present in the env;
  the token is read from the environment, never from code/config/context (CLAUDE.md §6).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

from adapters.base import Provider
from core.schema import CollectRequest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "instagram_post.json"

# The Apify actor that backs live collection. Recorded into source_method for audit.
APIFY_ACTOR = "apify/instagram-scraper"
# Apify addresses actors with "~" in the path (owner~name).
_APIFY_ACTOR_PATH = APIFY_ACTOR.replace("/", "~")
_RUN_SYNC_URL = f"https://api.apify.com/v2/acts/{_APIFY_ACTOR_PATH}/run-sync-get-dataset-items"


class FixtureProvider(Provider):
    """Replays a recorded scrape payload. Default in tests and no-token environments."""

    source_method = f"fixture:apify:{APIFY_ACTOR}"

    def __init__(self, fixture_path: Path = FIXTURE_PATH):
        self._fixture_path = fixture_path

    def fetch(self, request: CollectRequest) -> list[dict]:
        with open(self._fixture_path, encoding="utf-8") as fh:
            return json.load(fh)


class ApifyProvider(Provider):
    """Live Apify actor run. Requires APIFY_TOKEN in the environment.

    Returns exactly the shape FixtureProvider returns (a list of post dicts), so the
    adapter's normalization is identical whether collection is live or replayed.
    """

    source_method = f"apify:{APIFY_ACTOR}"

    def __init__(self, token: str | None = None, max_retries: int = 4):
        self._token = token or os.environ.get("APIFY_TOKEN")
        if not self._token:
            raise RuntimeError(
                "APIFY_TOKEN not set — live Instagram collection is unavailable. "
                "Use FixtureProvider for offline/test runs."
            )
        self._max_retries = max_retries

    def _actor_input(self, request: CollectRequest) -> dict:
        """Map our typed CollectRequest onto the actor's input schema."""
        result_type = "comments" if request.input_type.value == "post_url" else "posts"
        return {
            "directUrls": [request.target],
            "resultsType": "details",
            "resultsLimit": request.max_items,
            "addParentData": False,
            "maxComments": request.max_comments_per_post,
            "searchType": result_type,
        }

    def fetch(self, request: CollectRequest) -> list[dict]:  # pragma: no cover - live path
        # Resilient: retry transient failures with exponential backoff; never hammer or
        # block the pipeline on a flaky run (CLAUDE.md §2).
        payload = self._actor_input(request)
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = httpx.post(
                    _RUN_SYNC_URL,
                    params={"token": self._token},
                    json=payload,
                    timeout=300,
                )
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                if attempt == self._max_retries - 1:
                    break
                time.sleep(2**attempt)  # 1s, 2s, 4s, 8s
        raise RuntimeError(f"Apify Instagram collection failed after retries: {last_exc}")


def default_provider() -> Provider:
    """Pick the provider based on environment: live if a token exists, else fixture."""
    if os.environ.get("APIFY_TOKEN"):
        return ApifyProvider()
    return FixtureProvider()
