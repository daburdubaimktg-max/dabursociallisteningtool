"""Net Sentiment Score tests, including addition #2: lock the reach ≠ sentiment rule
in code by proving the KPI is computed from sentiment counts ONLY, with no engagement
input available to it at all.
"""

import inspect

from core.schema import SentimentLabel
from kpi import net_sentiment as ns
from kpi.net_sentiment import net_sentiment_from_labels, net_sentiment_score


def test_formula():
    # (positive − negative) / total
    assert net_sentiment_score(3, 1, 5) == 0.4
    assert net_sentiment_score(0, 0, 0) == 0.0  # empty handled honestly
    assert net_sentiment_score(2, 2, 4) == 0.0
    assert net_sentiment_score(0, 5, 5) == -1.0


def test_from_labels_counts_only():
    labels = [
        SentimentLabel.positive,
        SentimentLabel.positive,
        SentimentLabel.negative,
        SentimentLabel.neutral,
    ]
    net = net_sentiment_from_labels(labels)
    assert (net.positive, net.neutral, net.negative, net.total) == (2, 1, 1, 4)
    assert net.net_score == 0.25


def test_reach_is_not_an_input_to_sentiment():
    """ADDITION #2 — reach ≠ sentiment, enforced at the signature level.

    Neither KPI function may accept any engagement/reach parameter. If someone later
    tries to fold likes/views/shares/followers into Net Sentiment, this test fails.
    """
    reach_terms = {
        "like",
        "likes",
        "view",
        "views",
        "share",
        "shares",
        "save",
        "saves",
        "follower",
        "followers",
        "engagement",
        "reach",
        "metric",
        "metrics",
    }
    for fn in (net_sentiment_score, net_sentiment_from_labels):
        params = inspect.signature(fn).parameters
        for name in params:
            assert not any(term in name.lower() for term in reach_terms), (
                f"{fn.__name__} must not take a reach/engagement parameter; got '{name}'"
            )

    # And the module must not import Metrics (the engagement carrier) for the KPI.
    src = inspect.getsource(ns)
    assert "Metrics" not in src


def test_net_sentiment_ignores_engagement_weighting():
    """Two negative comments with huge like counts must NOT outweigh positives.

    Net Sentiment counts each scored comment once, regardless of engagement. (If reach
    leaked in, a high-like negative would drag the score down disproportionately.)
    """
    labels = [SentimentLabel.positive] * 3 + [SentimentLabel.negative] * 1
    # There is simply no place to pass like counts — that's the point.
    net = net_sentiment_from_labels(labels)
    assert net.net_score == 0.5  # (3 − 1) / 4, engagement-independent
