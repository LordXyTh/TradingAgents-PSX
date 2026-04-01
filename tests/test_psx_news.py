"""Tests for PSX news scraper — mocked unit tests + one live test."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from tradingagents.dataflows.psx_news import (
    PSX_COMPANY_NAMES,
    get_psx_announcements,
    get_psx_news_brecorder,
    get_news_psx,
    get_global_news_psx,
    _parse_date_flexible,
    _in_date_window,
)


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

SAMPLE_PSX_HTML = """
<html><body>
<table>
  <tr><td>25 Feb 2026</td><td>Financial Results — Q2 2026</td></tr>
  <tr><td>10 Jan 2026</td><td>Board Meeting Notice</td></tr>
  <tr><td>15 Dec 2025</td><td>Dividend Announcement</td></tr>
</table>
</body></html>
"""

SAMPLE_BR_SEARCH_HTML = """
<html><body>
<article>
  <h3><a href="/story/123">UBL posts record profits in Q2</a></h3>
  <span class="date">20 Mar 2026</span>
  <p>United Bank Limited reported a 25% increase in quarterly profits.</p>
</article>
<article>
  <h3><a href="/story/456">Banking sector outlook remains positive</a></h3>
  <span class="date">15 Mar 2026</span>
  <p>Analysts project strong growth for Pakistani banks.</p>
</article>
<article>
  <h3><a href="/story/789">Old banking news</a></h3>
  <span class="date">01 Jan 2025</span>
  <p>This article is too old and should be filtered out.</p>
</article>
</body></html>
"""

SAMPLE_BR_ECONOMY_HTML = """
<html><body>
<article class="story-item">
  <h3><a href="/economy/kse100-rallies">KSE-100 rallies 500 points on SBP rate cut</a></h3>
  <span class="date">28 Mar 2026</span>
  <p>The benchmark index gained 500 points following the monetary policy decision.</p>
</article>
<article class="story-item">
  <h3><a href="/economy/inflation">Inflation drops to single digits</a></h3>
  <span class="date">25 Mar 2026</span>
  <p>CPI inflation fell to 8.5% year-on-year in March 2026.</p>
</article>
</body></html>
"""

SAMPLE_DAWN_HTML = """
<html><body>
<article>
  <h2><a href="/news/12345/sbp-cuts-rate">SBP cuts policy rate by 100bps</a></h2>
  <span class="timestamp">27 Mar 2026</span>
  <p>State Bank of Pakistan reduced the key interest rate to 12%.</p>
</article>
</body></html>
"""


def _mock_response(html: str, status_code: int = 200):
    """Create a mock requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = html
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock


# ---------------------------------------------------------------------------
# Tests: _parse_date_flexible
# ---------------------------------------------------------------------------

class TestParseDateFlexible:
    def test_dmy_short_month(self):
        assert _parse_date_flexible("25 Feb 2026") == datetime(2026, 2, 25)

    def test_mdy_format(self):
        assert _parse_date_flexible("Feb 25, 2026") == datetime(2026, 2, 25)

    def test_iso_format(self):
        assert _parse_date_flexible("2026-02-25") == datetime(2026, 2, 25)

    def test_invalid_returns_none(self):
        assert _parse_date_flexible("not a date") is None

    def test_strips_whitespace(self):
        assert _parse_date_flexible("  25 Feb 2026  ") == datetime(2026, 2, 25)


# ---------------------------------------------------------------------------
# Tests: _in_date_window
# ---------------------------------------------------------------------------

class TestInDateWindow:
    def test_within_window(self):
        curr = datetime(2026, 3, 31)
        dt = datetime(2026, 3, 15)
        assert _in_date_window(dt, curr, 30) is True

    def test_outside_window(self):
        curr = datetime(2026, 3, 31)
        dt = datetime(2026, 1, 1)
        assert _in_date_window(dt, curr, 30) is False

    def test_none_date_included(self):
        curr = datetime(2026, 3, 31)
        assert _in_date_window(None, curr, 30) is True


# ---------------------------------------------------------------------------
# Tests: PSX_COMPANY_NAMES
# ---------------------------------------------------------------------------

class TestPSXCompanyNames:
    def test_has_minimum_30_entries(self):
        assert len(PSX_COMPANY_NAMES) >= 30

    def test_contains_key_tickers(self):
        for ticker in ["UBL", "HBL", "MCB", "BAHL", "ENGRO", "OGDC", "LUCK"]:
            assert ticker in PSX_COMPANY_NAMES, f"{ticker} missing from PSX_COMPANY_NAMES"


# ---------------------------------------------------------------------------
# Tests: get_psx_announcements
# ---------------------------------------------------------------------------

class TestGetPSXAnnouncements:
    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_returns_string(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PSX_HTML)
        result = get_psx_announcements("UBL", "2026-03-31", lookback_days=30)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_parses_financial_results(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PSX_HTML)
        result = get_psx_announcements("UBL", "2026-03-31", lookback_days=60)
        assert "Financial Results" in result or "financial" in result.lower()

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_filters_by_date(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PSX_HTML)
        # 10-day lookback from 2026-03-31 should NOT include Jan or Dec items
        result = get_psx_announcements("UBL", "2026-03-31", lookback_days=10)
        assert "Dividend Announcement" not in result
        assert "Board Meeting" not in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_handles_network_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        result = get_psx_announcements("UBL", "2026-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_strips_ka_suffix(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PSX_HTML)
        get_psx_announcements("UBL.KA", "2026-03-31")
        called_url = mock_get.call_args[0][0]
        assert "UBL" in called_url
        assert ".KA" not in called_url

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_empty_page(self, mock_get):
        mock_get.return_value = _mock_response("<html><body></body></html>")
        result = get_psx_announcements("UBL", "2026-03-31")
        assert isinstance(result, str)
        assert "No announcements" in result


# ---------------------------------------------------------------------------
# Tests: get_psx_news_brecorder
# ---------------------------------------------------------------------------

class TestGetPSXNewsBrecorder:
    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_returns_string(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_BR_SEARCH_HTML)
        result = get_psx_news_brecorder("UBL", "2026-03-31", lookback_days=30)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_extracts_articles(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_BR_SEARCH_HTML)
        result = get_psx_news_brecorder("UBL", "2026-03-31", lookback_days=30)
        assert "record profits" in result
        assert "Banking sector" in result.lower() or "banking" in result.lower()

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_filters_old_articles(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_BR_SEARCH_HTML)
        result = get_psx_news_brecorder("UBL", "2026-03-31", lookback_days=30)
        # Jan 2025 article should be filtered out
        assert "Old banking news" not in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_handles_network_error(self, mock_get):
        mock_get.side_effect = Exception("Timeout")
        result = get_psx_news_brecorder("UBL", "2026-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_uses_company_name(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_BR_SEARCH_HTML)
        get_psx_news_brecorder("UBL", "2026-03-31")
        called_url = mock_get.call_args[0][0]
        assert "United" in called_url or "Bank" in called_url


# ---------------------------------------------------------------------------
# Tests: get_news_psx (combined, main entry point)
# ---------------------------------------------------------------------------

class TestGetNewsPSX:
    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_returns_string(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PSX_HTML)
        result = get_news_psx("UBL", "2026-03-01", "2026-03-31")
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_fallback_on_bad_ticker(self, mock_get):
        mock_get.return_value = _mock_response("<html><body></body></html>")
        result = get_news_psx("XXXBADTICKER", "2026-03-01", "2026-03-31")
        assert isinstance(result, str)  # should not raise

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_combines_both_sources(self, mock_get):
        # First call = PSX announcements, second call = BR
        mock_get.side_effect = [
            _mock_response(SAMPLE_PSX_HTML),
            _mock_response(SAMPLE_BR_SEARCH_HTML),
        ]
        result = get_news_psx("UBL", "2026-02-01", "2026-03-31")
        assert "PSX Announcements" in result
        assert "Business Recorder" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_graceful_on_total_failure(self, mock_get):
        mock_get.side_effect = Exception("Network down")
        result = get_news_psx("UBL", "2026-03-01", "2026-03-31")
        assert isinstance(result, str)

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_bahl_returns_something(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_BR_SEARCH_HTML)
        result = get_news_psx("BAHL", "2026-03-01", "2026-03-31")
        assert isinstance(result, str)
        assert len(result) > 50 or "BAHL" in result or "Habib" in result


# ---------------------------------------------------------------------------
# Tests: get_global_news_psx
# ---------------------------------------------------------------------------

class TestGetGlobalNewsPSX:
    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_returns_string(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_BR_ECONOMY_HTML)
        result = get_global_news_psx("2026-03-31")
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_returns_macro_content(self, mock_get):
        # First call = BR economy, second = Dawn
        mock_get.side_effect = [
            _mock_response(SAMPLE_BR_ECONOMY_HTML),
            _mock_response(SAMPLE_DAWN_HTML),
        ]
        result = get_global_news_psx("2026-03-31")
        assert isinstance(result, str)
        assert len(result) > 100

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_includes_kse_or_sbp_content(self, mock_get):
        mock_get.side_effect = [
            _mock_response(SAMPLE_BR_ECONOMY_HTML),
            _mock_response(SAMPLE_DAWN_HTML),
        ]
        result = get_global_news_psx("2026-03-31")
        # Should contain KSE or SBP or inflation or economy content
        lower = result.lower()
        assert any(kw in lower for kw in ["kse", "sbp", "inflation", "rate", "economy", "market"])

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_graceful_on_failure(self, mock_get):
        mock_get.side_effect = Exception("All sites down")
        result = get_global_news_psx("2026-03-31")
        assert isinstance(result, str)
        assert "No macro news" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_respects_limit(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_BR_ECONOMY_HTML)
        result = get_global_news_psx("2026-03-31", look_back_days=7, limit=1)
        # Should have at most 1 article (1 "###" heading)
        assert result.count("###") <= 1


# ---------------------------------------------------------------------------
# Live test — actually hits dps.psx.com.pk (skip in CI)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLivePSXAnnouncements:
    def test_live_psx_announcements(self):
        """Hit dps.psx.com.pk live for UBL announcements."""
        result = get_psx_announcements("UBL", "2026-03-31", lookback_days=90)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should have either real announcements or a 'No announcements' note
        assert "UBL" in result or "No announcements" in result
