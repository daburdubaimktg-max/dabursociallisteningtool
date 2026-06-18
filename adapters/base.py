"""Adapter interface contract (CLAUDE.md §2).

One platform = one adapter = one folder. Adding a platform requires only a new
adapter conforming to this ABC — the pipeline downstream never changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from core.schema import CollectRequest, NormalizedRecord


class Provider(ABC):
    """The collection provider behind an adapter (Apify / Bright Data / official API).

    Adapters depend on this abstraction so the provider can be swapped without
    touching the pipeline or the adapter's normalization logic.
    """

    @abstractmethod
    def fetch(self, request: CollectRequest) -> list[dict]:
        """Return raw, provider-shaped payloads (one dict per post). This is bronze."""


class Adapter(ABC):
    """Every platform adapter implements this."""

    @abstractmethod
    def collect(self, request: CollectRequest) -> Iterable[NormalizedRecord]:
        """Collect and normalize.

        Must:
          - emit records conforming to the NormalizedRecord schema,
          - stamp collected_at + source_method on every record,
          - be idempotent and resilient (never block the pipeline on one bad post),
          - read secrets from env, never from code/config/context.
        """

    @abstractmethod
    def raw_payloads(self, request: CollectRequest) -> list[dict]:
        """Expose the raw provider payloads so the pipeline can persist bronze."""
