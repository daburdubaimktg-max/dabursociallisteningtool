"""The NLP service contract (CLAUDE.md §3).

This is the executable spec that BOTH the stub and the future self-hosted transformer
service must pass — it validates the GPU swap-in against the same behaviour. To validate
the real service later, parametrize `service` over it here.
"""

import pytest

from core.schema import Sentiment, SentimentLabel
from nlp.contract import Detection, NLPService
from nlp.stub import StubNLPService


@pytest.fixture(params=[StubNLPService])
def service(request) -> NLPService:
    return request.param()


def test_satisfies_protocol(service):
    assert isinstance(service, NLPService)


def test_detect_returns_detection(service):
    d = service.detect("Love this!")
    assert isinstance(d, Detection)
    assert d.language
    assert 0.0 <= d.confidence <= 1.0


def test_detect_arabic_script(service):
    assert service.detect("هذا المنتج رائع جدا").language == "ar"


def test_detect_arabizi_not_english(service):
    # Latin-script Arabic must route to the Arabic path, never be called English.
    assert service.detect("wallah 7elo ktir 3ajabni").language == "arabizi"


def test_detect_plain_english(service):
    assert service.detect("when is this available").language == "en"


def test_score_returns_sentiment_with_model_version(service):
    s = service.score("Love this so much, best ever!", "en")
    assert isinstance(s, Sentiment)
    assert s.label in set(SentimentLabel)
    assert -1.0 <= s.score <= 1.0
    assert 0.0 <= s.confidence <= 1.0
    assert s.model_version  # MUST be stamped on every scored record


def test_stub_model_version_is_marked():
    # Stub records must be identifiable/excludable from real reporting.
    assert StubNLPService().score("great", "en").model_version == "stub"


def test_score_polarity(service):
    assert service.score("Love this, amazing!", "en").label is SentimentLabel.positive
    assert service.score("fake and terrible, it leaks", "en").label is SentimentLabel.negative
    assert service.score("when is this available", "en").label is SentimentLabel.neutral


def test_translate_is_cached_and_display_only(service):
    a = service.translate("هذا المنتج رائع", "ar")
    b = service.translate("هذا المنتج رائع", "ar")
    assert a == b  # cached on text hash
    assert isinstance(a, str) and a
