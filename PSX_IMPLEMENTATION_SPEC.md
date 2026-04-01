# PSX Implementation Spec — TradingAgents Fork

## Goal
Extend TradingAgents to support PSX (Pakistan Stock Exchange) stocks alongside existing US/TSX support. Fit cleanly into the existing vendor architecture.

## Architecture Overview

The framework uses a vendor-routing pattern in `tradingagents/dataflows/`:
- `interface.py` — routes method calls to vendor implementations
- `default_config.py` — sets default vendors per category
- Vendors: `yfinance`, `alpha_vantage` (existing) → add `psx` (new)

## Three Implementation Tracks

---

## Track 1: Ticker Normalizer + PSX Price Data
**File to create:** `tradingagents/dataflows/psx_stock.py`
**Files to modify:** `tradingagents/dataflows/interface.py`, `tradingagents/dataflows/config.py`

### Problem
PSX tickers on yfinance use `.KA` suffix (e.g. `UBL.KA`, `BAHL.KA`) but users pass bare tickers (`UBL`, `BAHL`). The framework needs to detect PSX tickers and normalize them.

### Implementation

**`psx_stock.py`** — wraps yfinance with PSX-aware ticker normalization:

```python
# Key functions to implement:

def normalize_psx_ticker(symbol: str) -> str:
    """Append .KA suffix if not already present and ticker is PSX."""
    if not symbol.upper().endswith('.KA'):
        return f"{symbol.upper()}.KA"
    return symbol.upper()

def is_psx_ticker(symbol: str) -> bool:
    """Detect if a ticker is PSX-listed."""
    return symbol.upper().endswith('.KA') or symbol.upper() in PSX_TICKER_LIST

def get_psx_stock_data(symbol, start_date, end_date):
    """OHLCV data for PSX tickers via yfinance with .KA normalization."""
    # normalize → call yfinance → return same format as y_finance.py

def get_psx_indicators(symbol, indicator, curr_date, look_back_days):
    """Technical indicators for PSX via stockstats (same as yfinance path)."""
    # normalize ticker → reuse existing stockstats logic

def get_psx_fundamentals(ticker, curr_date=None):
    """Fundamentals from yfinance (.KA) — partial but usable."""
    # normalize → yf.Ticker → same fields as y_finance.get_fundamentals

def get_psx_balance_sheet(ticker, freq="quarterly", curr_date=None):
    """Balance sheet via yfinance .KA"""

def get_psx_cashflow(ticker, freq="quarterly", curr_date=None):
    """Cash flow via yfinance .KA"""

def get_psx_income_statement(ticker, freq="quarterly", curr_date=None):
    """Income statement via yfinance .KA"""

def get_psx_insider_transactions(ticker):
    """
    PSX insider/director disclosures scraped from dps.psx.com.pk/company/{ticker}
    announcements section (type: Others, filter disclosure keywords).
    Returns text summary if available, empty note if not.
    """
```

**`PSX_TICKER_LIST`** — maintain a list of ~KSE-100 symbols (without .KA) for auto-detection.

### Wire into interface.py
Add `psx` to `VENDOR_LIST` and `VENDOR_METHODS` for all categories:
```python
"get_stock_data": {
    "alpha_vantage": ...,
    "yfinance": ...,
    "psx": get_psx_stock_data,   # ADD
},
# same for indicators, fundamentals, balance_sheet, cashflow, income_statement, insider_transactions
```

### Tests (create `tests/test_psx_stock.py`)
```python
def test_normalize_psx_ticker():
    assert normalize_psx_ticker("UBL") == "UBL.KA"
    assert normalize_psx_ticker("UBL.KA") == "UBL.KA"
    assert normalize_psx_ticker("bahl") == "BAHL.KA"

def test_is_psx_ticker():
    assert is_psx_ticker("UBL.KA") == True
    assert is_psx_ticker("UBL") == True   # in KSE-100 list
    assert is_psx_ticker("AAPL") == False

def test_get_psx_stock_data_returns_ohlcv():
    result = get_psx_stock_data("UBL", "2026-03-01", "2026-03-31")
    assert "Close" in result
    assert "UBL.KA" in result

def test_get_psx_fundamentals_has_pe():
    result = get_psx_fundamentals("UBL")
    assert "PE Ratio" in result

def test_psx_indicators_rsi():
    result = get_psx_indicators("UBL", "rsi", "2026-03-31", 14)
    assert "rsi" in result.lower()
```

---

## Track 2: PSX News Scraper
**File to create:** `tradingagents/dataflows/psx_news.py`
**Files to modify:** `tradingagents/dataflows/interface.py`

### Problem
yfinance returns 0 news items for PSX tickers. The sentiment and news analyst agents are blind. We need to scrape Business Recorder and Dawn Business for PSX company news.

### Sources
1. **Business Recorder** — `https://www.brecorder.com/search/{COMPANY_NAME}` or tag pages
2. **Dawn Business** — `https://www.dawn.com/business` + search
3. **PSX Announcements** — `https://dps.psx.com.pk/company/{TICKER}` announcements section (structured, most reliable)

### Implementation

```python
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# PSX company name mapping for search
PSX_COMPANY_NAMES = {
    "UBL": "United Bank",
    "BAHL": "Bank AL Habib",
    "HBL": "Habib Bank",
    "MCB": "MCB Bank",
    "ENGRO": "Engro",
    # ... extend for KSE-100
}

def get_psx_announcements(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """
    Scrape PSX official announcements for a ticker.
    Source: dps.psx.com.pk/company/{TICKER} announcements section.
    Returns formatted string of announcement titles + dates.
    """

def get_psx_news_brecorder(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """
    Scrape Business Recorder for company news.
    Returns formatted news items with date, title, snippet.
    """

def get_news_psx(
    ticker: str,
    curr_date: str,
    lookback_days: int = 7
) -> str:
    """
    Main entry point. Combines PSX announcements + BR news.
    Falls back gracefully if scraping fails.
    Same signature as get_news_yfinance.
    """

def get_global_news_psx(curr_date: str, lookback_days: int = 7) -> str:
    """
    Pakistan macro/market news (KSE-100 index, SBP policy, economy).
    Scrapes Dawn Business / BR for macro context.
    Same signature as get_global_news_yfinance.
    """
```

### Wire into interface.py
```python
from .psx_news import get_news_psx, get_global_news_psx

"get_news": {
    "alpha_vantage": ...,
    "yfinance": ...,
    "psx": get_news_psx,      # ADD
},
"get_global_news": {
    "yfinance": ...,
    "alpha_vantage": ...,
    "psx": get_global_news_psx,  # ADD
},
```

### Tests (create `tests/test_psx_news.py`)
```python
def test_get_psx_announcements_returns_string():
    result = get_psx_announcements("UBL", "2026-03-31", lookback_days=30)
    assert isinstance(result, str)
    assert len(result) > 0

def test_get_psx_announcements_has_financial_results():
    # UBL posted financial results Feb 25, 2026 — should appear
    result = get_psx_announcements("UBL", "2026-03-31", lookback_days=60)
    assert "Financial Results" in result or "financial" in result.lower()

def test_get_news_psx_fallback_on_bad_ticker():
    # Should not raise, just return empty/note
    result = get_news_psx("XXXBADTICKER", "2026-03-31")
    assert isinstance(result, str)

def test_get_global_news_psx_returns_macro():
    result = get_global_news_psx("2026-03-31")
    assert isinstance(result, str)
    assert len(result) > 100

def test_get_news_psx_bahl():
    result = get_news_psx("BAHL", "2026-03-31", lookback_days=30)
    assert isinstance(result, str)
    # Should mention BAHL or Bank AL Habib
    assert "BAHL" in result or "Habib" in result or len(result) > 50
```

---

## Track 3: Config + Integration + End-to-End Test
**Files to modify:** `tradingagents/default_config.py`, `tradingagents/dataflows/config.py`
**File to create:** `tests/test_psx_integration.py`

### Problem
No way to tell the framework "this is a PSX stock, use PSX vendors". Need a market-aware config pattern that auto-routes based on ticker or explicit market setting.

### Implementation

**`default_config.py`** — add PSX profile:
```python
# Add PSX vendor config
PSX_CONFIG = {
    **DEFAULT_CONFIG,
    "data_vendors": {
        "core_stock_apis": "psx",
        "technical_indicators": "psx",
        "fundamental_data": "psx",
        "news_data": "psx",
    },
}

# Add market auto-detection helper
def get_config_for_ticker(ticker: str) -> dict:
    """
    Auto-detect market from ticker and return appropriate config.
    UBL / BAHL / ENGRO etc → PSX_CONFIG
    AAPL / MSFT etc → DEFAULT_CONFIG
    TD / RY etc + .TO suffix → DEFAULT_CONFIG (yfinance handles TSX natively)
    """
    from tradingagents.dataflows.psx_stock import is_psx_ticker
    if is_psx_ticker(ticker):
        return PSX_CONFIG.copy()
    return DEFAULT_CONFIG.copy()
```

**`config.py`** — ensure config is accessible in dataflows (already exists, just verify PSX vendors are handled).

### End-to-End Test (tests/test_psx_integration.py)
```python
"""
Integration test: run TradingAgentsGraph on UBL/BAHL and verify
all agents produce non-empty output.
Requires: ANTHROPIC_API_KEY (or any supported provider key)
"""
import pytest
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import get_config_for_ticker

@pytest.mark.integration   # mark so unit tests don't run this (costs API $)
def test_ubl_full_analysis():
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
    config = get_config_for_ticker("BAHL")
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1

    ta = TradingAgentsGraph(debug=True, config=config)
    state, decision = ta.propagate("BAHL", "2026-03-31")
    assert decision is not None

def test_get_config_for_ticker_psx():
    config = get_config_for_ticker("UBL")
    assert config["data_vendors"]["news_data"] == "psx"

def test_get_config_for_ticker_us():
    config = get_config_for_ticker("AAPL")
    assert config["data_vendors"]["news_data"] == "yfinance"

def test_get_config_for_ticker_tsx():
    config = get_config_for_ticker("TD")
    assert config["data_vendors"]["news_data"] == "yfinance"
```

---

## File Map (what gets created/modified)

```
tradingagents/
  dataflows/
    psx_stock.py          ← NEW (Track 1)
    psx_news.py           ← NEW (Track 2)
    interface.py          ← MODIFY: add psx to VENDOR_LIST + VENDOR_METHODS
    config.py             ← VERIFY: no changes needed likely
  default_config.py       ← MODIFY: add PSX_CONFIG + get_config_for_ticker (Track 3)

tests/
  test_psx_stock.py       ← NEW (Track 1)
  test_psx_news.py        ← NEW (Track 2)
  test_psx_integration.py ← NEW (Track 3)

PSX_IMPLEMENTATION_SPEC.md  ← THIS FILE
```

## Quality Bar
- All unit tests pass without API keys
- Integration tests pass with ANTHROPIC_API_KEY set
- No breaking changes to existing US/TSX functionality
- Existing tests in tests/ still pass
- Graceful fallback: if PSX scraping fails → return informative empty string, don't raise

## Existing Tests
Run `pytest tests/ -v -k "not integration"` to verify no regressions.
