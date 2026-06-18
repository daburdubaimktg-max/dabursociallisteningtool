"""The normalized schema — the contract every adapter emits and the pipeline consumes.

This mirrors CLAUDE.md §1 exactly. If you change a field here, change it in CLAUDE.md too.
Fields are nullable where a platform does not expose them.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Platform(str, Enum):
    instagram = "instagram"
    tiktok = "tiktok"
    youtube = "youtube"
    reddit = "reddit"
    x = "x"


class MediaType(str, Enum):
    image = "image"
    video = "video"
    text = "text"


class InputType(str, Enum):
    post_url = "post_url"
    handle = "handle"
    watch = "watch"


class SentimentLabel(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"


class Metrics(BaseModel):
    likes: Optional[int] = None
    comments_count: Optional[int] = None
    views: Optional[int] = None
    shares: Optional[int] = None
    saves: Optional[int] = None


class Sentiment(BaseModel):
    label: SentimentLabel
    score: float
    confidence: float
    # MUST be stamped on every scored record. Stub scores carry "stub" so they are
    # identifiable and excludable from real reporting (CLAUDE.md §3).
    model_version: str


class Comment(BaseModel):
    comment_id: str
    author: Optional[str] = None
    text_raw: str
    likes: Optional[int] = None
    replied_to: Optional[str] = None
    posted_at: Optional[str] = None

    # Enrichment populated by the pipeline (not by the adapter).
    detected_language: Optional[str] = None
    detected_dialect: Optional[str] = None
    text_en: Optional[str] = None  # display only — NEVER fed to the scorer (Rule 1)
    sentiment: Optional[Sentiment] = None


class Flags(BaseModel):
    is_spam: bool = False
    is_bot_suspected: bool = False
    is_counterfeit_mention: bool = False
    is_complaint: bool = False


class NormalizedRecord(BaseModel):
    post_id: str
    platform: Platform
    author_handle: Optional[str] = None
    author_id: Optional[str] = None
    author_follower_count: Optional[int] = None
    url: str
    posted_at: Optional[str] = None
    collected_at: str
    source_method: str
    caption_or_title: Optional[str] = None
    media_type: Optional[MediaType] = None
    metrics: Metrics = Field(default_factory=Metrics)
    comments: list[Comment] = Field(default_factory=list)

    # Post-level enrichment.
    detected_language: Optional[str] = None
    detected_dialect: Optional[str] = None
    text_en: Optional[str] = None
    brand_tags: list[str] = Field(default_factory=list)
    market_tags: list[str] = Field(default_factory=list)
    sentiment: Optional[Sentiment] = None
    topics: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    emojis: list[str] = Field(default_factory=list)
    flags: Flags = Field(default_factory=Flags)

    @property
    def dedup_key(self) -> str:
        """Dedup is on platform + native id (CLAUDE.md §1)."""
        return f"{self.platform.value}:{self.post_id}"


class CollectRequest(BaseModel):
    """The typed job description every adapter accepts (CLAUDE.md §2)."""

    input_type: InputType
    target: str  # a post URL, a handle, or a watch term
    platform: Platform
    date_window_days: Optional[int] = None
    max_items: int = 30
    max_comments_per_post: int = 100
    brands: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)
