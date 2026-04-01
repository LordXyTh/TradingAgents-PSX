"""
PSX integration and config tests.

Unit tests (no API keys): verify get_config_for_ticker routing.
Integration tests (@pytest.mark.integration): full TradingAgentsGraph runs on PSX tickers.
"""

from unittest.mock import patch

import pytest

from tradingagents.default_config import DEFAULT_CONFIG, PSX_CONFIG, get_config_for_ticker


# ---------------------------------------------------------------------------
# Mock is_psx_ticker so unit tests work even if Track 1 (psx_stock.py)
# hasn't been merged yet.  Mimics the spec: returns True for .KA suffix
# or symbols in the KSE-100 list.
# ---------------------------------------------------------------------------
_MOCK_PSX_TICKERS = {
    "UBL", "BAHL", "HBL", "MCB", "ENGRO", "LUCK", "PSO", "OGDC", "PPL",
    "FFC", "HUBC", "EFERT", "MEBL", "NBP", "ABL", "BAFL", "FABL",
}


def _mock_is_psx_ticker(symbol: str) -> bool:
    return symbol.upper().endswith(".KA") or symbol.upper() in _MOCK_PSX_TICKERS


# ---------------------------------------------------------------------------
# Unit tests — no API keys required
# ---------------------------------------------------------------------------


@patch("tradingagents.default_config.is_psx_ticker", create=True)
def test_get_config_for_ticker_psx(mock_fn):
    """PSX ticker should return PSX_CONFIG with all vendors set to 'psx'."""
    with patch(
        "tradingagents.dataflows.psx_stock.is_psx_ticker",
        side_effect=_mock_is_psx_ticker,
        create=True,
    ):
        config = get_config_for_ticker("UBL")
    assert config["data_vendors"]["news_data"] == "psx"
    assert config["data_vendors"]["core_stock_apis"] == "psx"
    assert config["data_vendors"]["technical_indicators"] == "psx"
    assert config["data_vendors"]["fundamental_data"] == "psx"


@patch(
    "tradingagents.dataflows.psx_stock.is_psx_ticker",
    side_effect=_mock_is_psx_ticker,
    create=True,
)
def test_get_config_for_ticker_us(mock_fn):
    """US ticker should return DEFAULT_CONFIG (yfinance vendors)."""
    config = get_config_for_ticker("AAPL")
    assert config["data_vendors"]["news_data"] == "yfinance"
    assert config["data_vendors"]["core_stock_apis"] == "yfinance"


@patch(
    "tradingagents.dataflows.psx_stock.is_psx_ticker",
    side_effect=_mock_is_psx_ticker,
    create=True,
)
def test_get_config_for_ticker_tsx(mock_fn):
    """TSX ticker (e.g. TD) should return DEFAULT_CONFIG — yfinance handles TSX natively."""
    config = get_config_for_ticker("TD")
    assert config["data_vendors"]["news_data"] == "yfinance"


@patch(
    "tradingagents.dataflows.psx_stock.is_psx_ticker",
    side_effect=_mock_is_psx_ticker,
    create=True,
)
def test_get_config_for_ticker_psx_with_suffix(mock_fn):
    """Ticker already carrying .KA suffix should still route to PSX_CONFIG."""
    config = get_config_for_ticker("UBL.KA")
    assert config["data_vendors"]["news_data"] == "psx"


def test_psx_config_inherits_defaults():
    """PSX_CONFIG should inherit non-vendor keys from DEFAULT_CONFIG."""
    assert PSX_CONFIG["llm_provider"] == DEFAULT_CONFIG["llm_provider"]
    assert PSX_CONFIG["max_debate_rounds"] == DEFAULT_CONFIG["max_debate_rounds"]


def test_get_config_for_ticker_returns_copy():
    """Returned config should be a copy, not a reference to the global."""
    with patch(
        "tradingagents.dataflows.psx_stock.is_psx_ticker",
        side_effect=_mock_is_psx_ticker,
        create=True,
    ):
        config = get_config_for_ticker("UBL")
    config["llm_provider"] = "mutated"
    assert PSX_CONFIG["llm_provider"] != "mutated"


# ---------------------------------------------------------------------------
# Integration tests — require API keys, skip with: pytest -k "not integration"
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_ubl_full_analysis():
    """End-to-end: run full TradingAgentsGraph analysis on UBL."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    config = get_config_for_ticker("UBL")
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["llm_provider"] = "anthropic"
    config["deep_think_llm"] = "claude-sonnet-4-6"
    config["quick_think_llm"] = "claude-sonnet-4-6"

    ta = TradingAgentsGraph(debug=True, config=config)
    state, decision = ta.propagate("UBL", "2026-03-31")

    assert decision is not None
    assert "BUY" in decision or "SELL" in decision or "HOLD" in decision


@pytest.mark.integration
def test_bahl_full_analysis():
    """End-to-end: run full TradingAgentsGraph analysis on BAHL."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    config = get_config_for_ticker("BAHL")
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1

    ta = TradingAgentsGraph(debug=True, config=config)
    state, decision = ta.propagate("BAHL", "2026-03-31")
    assert decision is not None
