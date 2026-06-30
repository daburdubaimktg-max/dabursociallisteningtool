"""Models for competitor follower-growth tracking.

These are deliberately a *reach* dimension only (CLAUDE.md Rule 2). A
`FollowerSnapshot` is one reading of one brand's follower count on one platform
for one period. Everything downstream (growth, leaderboards, the Excel
dashboard) is computed from snapshots and carries no sentiment.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class GrowthPlatform(str, Enum):
    instagram = "instagram"
    tiktok = "tiktok"


class Competitor(BaseModel):
    """A tracked competitor brand and its handles — config-as-data (CLAUDE.md §6).

    A brand may live on one or both platforms; the missing handle is null.
    """

    brand: str
    category: Optional[str] = None
    region: Optional[str] = None
    instagram_handle: Optional[str] = None
    tiktok_handle: Optional[str] = None

    def handle_for(self, platform: GrowthPlatform) -> Optional[str]:
        return self.instagram_handle if platform is GrowthPlatform.instagram else self.tiktok_handle


class FollowerSnapshot(BaseModel):
    """One follower-count reading. Dedup key = platform + handle + period.

    `period` is a calendar month, "YYYY-MM" — follower tracking is monthly, matching
    the source tracker. Re-collecting the same month updates the count in place
    (idempotent), it does not create a duplicate row.
    """

    platform: GrowthPlatform
    handle: str
    brand: str
    category: Optional[str] = None
    region: Optional[str] = None
    period: str  # "YYYY-MM"
    follower_count: int = Field(ge=0)
    collected_at: Optional[str] = None
    source_method: Optional[str] = None

    @field_validator("period")
    @classmethod
    def _check_period(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}", v):
            raise ValueError(f"period must be 'YYYY-MM', got {v!r}")
        return v

    @property
    def dedup_key(self) -> str:
        return f"{self.platform.value}:{self.handle}:{self.period}"


class GrowthPoint(BaseModel):
    """Month-over-month growth for one brand on one platform between two periods."""

    platform: GrowthPlatform
    brand: str
    category: Optional[str] = None
    region: Optional[str] = None
    period: str
    followers: int
    prev_followers: Optional[int] = None
    delta: Optional[int] = None  # followers − prev_followers
    pct_change: Optional[float] = None  # delta / prev_followers, rounded to 4 dp


class LeaderboardRow(BaseModel):
    """A brand's growth over a window, for the headline leaderboard."""

    brand: str
    platform: GrowthPlatform
    category: Optional[str] = None
    region: Optional[str] = None
    start_period: str
    end_period: str
    start_followers: int
    end_followers: int
    delta: int
    pct_change: Optional[float]
