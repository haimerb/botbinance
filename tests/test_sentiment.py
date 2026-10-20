from src.strategy.sentiment import SentimentAnalyzer


def make_analyzer(enabled=True):
    import src.strategy.sentiment as s
    s.SENTIMENT_ENABLED = enabled
    analyzer = SentimentAnalyzer()
    return analyzer


def test_disabled_returns_neutral():
    import src.strategy.sentiment as s
    original = s.SENTIMENT_ENABLED
    s.SENTIMENT_ENABLED = False
    try:
        analyzer = SentimentAnalyzer()
        result = analyzer.get_sentiment("BTCUSDT")
        assert result["label"] == "NEUTRAL"
        assert result["source"] == "disabled"
    finally:
        s.SENTIMENT_ENABLED = original


def test_score_text_positive():
    analyzer = SentimentAnalyzer()
    score = analyzer._score_text("Bitcoin surge to record high as institutional adoption grows")
    assert score > 0


def test_score_text_negative():
    analyzer = SentimentAnalyzer()
    score = analyzer._score_text("Crypto exchange hacked, massive sell-off and crash follows")
    assert score < 0


def test_filter_signal_disabled_passthrough():
    import src.strategy.sentiment as s
    original = s.SENTIMENT_ENABLED
    s.SENTIMENT_ENABLED = False
    try:
        analyzer = SentimentAnalyzer()
        signal, reason = analyzer.filter_signal("BTCUSDT", "BUY")
        assert signal == "BUY"
        assert reason == ""
    finally:
        s.SENTIMENT_ENABLED = original


def test_filter_signal_blocks_buy_on_negative():
    import src.strategy.sentiment as s
    original = s.SENTIMENT_ENABLED
    s.SENTIMENT_ENABLED = True
    try:
        analyzer = SentimentAnalyzer()
        analyzer._cache["BTCUSDT"] = {"score": -5, "label": "NEGATIVE", "articles": 10, "source": "test"}
        import time
        analyzer._cache_time["BTCUSDT"] = time.time()
        signal, reason = analyzer.filter_signal("BTCUSDT", "BUY")
        assert signal == "HOLD"
        assert "negativo" in reason
    finally:
        s.SENTIMENT_ENABLED = original