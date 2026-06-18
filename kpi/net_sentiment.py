"""Net Sentiment Score (CLAUDE.md §4).

    Net Sentiment Score = (positive − negative) ÷ total

LOAD-BEARING (Rule 2 — reach ≠ sentiment): these functions take sentiment counts /
labels ONLY. There is deliberately NO parameter for likes, views, shares, follower
count, or any engagement signal. Sentiment is computed from sentiment alone; engagement
is reported separately. Do not add an engagement argument here.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from core.schema import SentimentLabel


class NetSentiment(BaseModel):
    positive: int
    neutral: int
    negative: int
    total: int
    net_score: float  # (positive − negative) / total, in [-1, 1]; 0.0 when total == 0


def net_sentiment_score(positive: int, negative: int, total: int) -> float:
    """The bare formula. Engagement is intentionally absent."""
    if total <= 0:
        return 0.0
    return (positive - negative) / total


def net_sentiment_from_labels(labels: list[SentimentLabel]) -> NetSentiment:
    """Roll a list of sentiment labels into the KPI. Input is labels only."""
    counts = Counter(labels)
    pos = counts.get(SentimentLabel.positive, 0)
    neu = counts.get(SentimentLabel.neutral, 0)
    neg = counts.get(SentimentLabel.negative, 0)
    total = pos + neu + neg
    return NetSentiment(
        positive=pos,
        neutral=neu,
        negative=neg,
        total=total,
        net_score=round(net_sentiment_score(pos, neg, total), 4),
    )
