"""Tests for PSX news scraper — mocked unit tests + one live test."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from tradingagents.dataflows.psx_news import (
    PSX_COMPANY_NAMES,
    get_psx_announcements,
    get_psx_news_brecorder,
    get_psx_news_propakistani,
    get_psx_news_profit,
    get_psx_news_thenews,
    get_sbp_press_releases,
    get_news_psx,
    get_global_news_psx,
    _parse_date_flexible,
    _in_date_window,
    _strip_trailing_junk,
    _REQUEST_TIMEOUT,
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
  <tr><td></td><td>CEO Name Here</td></tr>
  <tr><td></td><td>Chairperson of the Board</td></tr>
</table>
</body></html>
"""

SAMPLE_PSX_HTML_VIEWPDF = """
<html><body>
<table>
  <tr><td>25 Feb 2026</td><td>Financial Results — Q2 2026 ViewPDF</td></tr>
  <tr><td>10 Jan 2026</td><td>Board Meeting Notice View</td></tr>
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

SAMPLE_PROPAKISTANI_HTML = """
<html><body>
<article class="post-item">
  <h3 class="post-title"><a href="/2026/03/20/ubl-digital-banking/">UBL Launches Digital Banking Platform</a></h3>
  <time>20 Mar 2026</time>
</article>
<article class="post-item">
  <h3 class="post-title"><a href="/2026/03/10/fintech-update/">Pakistan Fintech Landscape Evolves</a></h3>
  <time>10 Mar 2026</time>
</article>
</body></html>
"""

SAMPLE_PROFIT_HTML = """
<html><body>
<article class="post-entry">
  <h2><a href="/2026/03/18/ubl-earnings/">UBL earnings beat expectations</a></h2>
  <time>18 Mar 2026</time>
</article>
</body></html>
"""

SAMPLE_THENEWS_HTML = """
<html><body>
<div class="search-listing">
  <h3><a href="/print/123456">Banking sector profits surge in Q1</a></h3>
  <span class="date">22 Mar 2026</span>
</div>
<div class="search-listing">
  <h3><a href="/print/123457">PSX index hits all-time high</a></h3>
  <span class="date">21 Mar 2026</span>
</div>
</body></html>
"""

SAMPLE_SBP_HTML = """
<html><body>
<table>
  <tr>
    <td>25 Mar 2026</td>
    <td><a href="/press/pr-25Mar26.pdf">Monetary Policy Decision - SBP maintains policy rate at 12%</a></td>
  </tr>
  <tr>
    <td>28 Jan 2026</td>
    <td><a href="/press/pr-28Jan26.pdf">Monetary Policy Decision - SBP cuts rate by 100bps</a></td>
  </tr>
</table>
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
# Tests: timeout constant
# ---------------------------------------------------------------------------

class TestTimeoutConstant:
    def test_timeout_is_8_seconds(self):
        assert _REQUEST_TIMEOUT == 8


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
# Tests: _strip_trailing_junk
# ---------------------------------------------------------------------------

class TestStripTrailingJunk:
    def test_strips_viewpdf(self):
        assert _strip_trailing_junk("Financial Results ViewPDF") == "Financial Results"

    def test_strips_view(self):
        assert _strip_trailing_junk("Board Meeting Notice View") == "Board Meeting Notice"

    def test_no_junk_unchanged(self):
        assert _strip_trailing_junk("Normal title") == "Normal title"


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
        result = get_psx_announcements("UBL", "2026-03-31", lookback_days=60)
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
        get_psx_announcements("UBL.KA", "2026-03-31", lookback_days=60)
        called_url = mock_get.call_args[0][0]
        assert "UBL" in called_url
        assert ".KA" not in called_url

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_empty_page(self, mock_get):
        mock_get.return_value = _mock_response("<html><body></body></html>")
        result = get_psx_announcements("UBL", "2026-03-31")
        assert isinstance(result, str)
        assert "No announcements" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_skips_ceo_rows(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PSX_HTML)
        result = get_psx_announcements("UBL", "2026-03-31", lookback_days=120)
        assert "CEO" not in result
        assert "Chairperson" not in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_strips_viewpdf(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PSX_HTML_VIEWPDF)
        result = get_psx_announcements("UBL", "2026-03-31", lookback_days=60)
        assert "ViewPDF" not in result
        # The View at end of "Board Meeting Notice View" should also be stripped
        assert result.count("View") == 0 or "View" not in result.split("Notice")[-1]

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_skips_items_without_date(self, mock_get):
        html = """<html><body><table>
        <tr><td>No date here</td><td>Some announcement</td></tr>
        <tr><td>25 Feb 2026</td><td>Real announcement</td></tr>
        </table></body></html>"""
        mock_get.return_value = _mock_response(html)
        result = get_psx_announcements("UBL", "2026-03-31", lookback_days=60)
        assert "Some announcement" not in result
        assert "Real announcement" in result


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
# Tests: get_psx_news_propakistani
# ---------------------------------------------------------------------------

class TestGetPSXNewsProPakistani:
    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_returns_string(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PROPAKISTANI_HTML)
        result = get_psx_news_propakistani("UBL", "2026-03-31", lookback_days=30)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_extracts_articles(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PROPAKISTANI_HTML)
        result = get_psx_news_propakistani("UBL", "2026-03-31", lookback_days=30)
        assert "Digital Banking" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_handles_network_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        result = get_psx_news_propakistani("UBL", "2026-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_empty_page(self, mock_get):
        mock_get.return_value = _mock_response("<html><body></body></html>")
        result = get_psx_news_propakistani("UBL", "2026-03-31")
        assert isinstance(result, str)
        assert "No recent news" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_uses_correct_url(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PROPAKISTANI_HTML)
        get_psx_news_propakistani("UBL", "2026-03-31")
        called_url = mock_get.call_args[0][0]
        assert "propakistani.pk" in called_url
        assert "United" in called_url or "Bank" in called_url


# ---------------------------------------------------------------------------
# Tests: get_psx_news_profit
# ---------------------------------------------------------------------------

class TestGetPSXNewsProfit:
    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_returns_string(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PROFIT_HTML)
        result = get_psx_news_profit("UBL", "2026-03-31", lookback_days=30)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_extracts_articles(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PROFIT_HTML)
        result = get_psx_news_profit("UBL", "2026-03-31", lookback_days=30)
        assert "earnings" in result.lower()

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_handles_network_error(self, mock_get):
        mock_get.side_effect = Exception("Timeout")
        result = get_psx_news_profit("UBL", "2026-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_uses_correct_url(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_PROFIT_HTML)
        get_psx_news_profit("UBL", "2026-03-31")
        called_url = mock_get.call_args[0][0]
        assert "profit.pakistantoday" in called_url


# ---------------------------------------------------------------------------
# Tests: get_psx_news_thenews
# ---------------------------------------------------------------------------

class TestGetPSXNewsTheNews:
    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_returns_string(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_THENEWS_HTML)
        result = get_psx_news_thenews("UBL", "2026-03-31", lookback_days=30)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_extracts_articles(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_THENEWS_HTML)
        result = get_psx_news_thenews("UBL", "2026-03-31", lookback_days=30)
        assert "Banking sector" in result or "PSX index" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_handles_network_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        result = get_psx_news_thenews("UBL", "2026-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_uses_correct_url(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_THENEWS_HTML)
        get_psx_news_thenews("UBL", "2026-03-31")
        called_url = mock_get.call_args[0][0]
        assert "thenews.com.pk" in called_url
        assert "cat=3" in called_url


# ---------------------------------------------------------------------------
# Tests: get_sbp_press_releases
# ---------------------------------------------------------------------------

class TestGetSBPPressReleases:
    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_returns_string(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_SBP_HTML)
        result = get_sbp_press_releases("2026-03-31", lookback_days=30)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_extracts_monetary_policy(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_SBP_HTML)
        result = get_sbp_press_releases("2026-03-31", lookback_days=30)
        assert "Monetary Policy" in result or "policy rate" in result.lower()

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_filters_by_date(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_SBP_HTML)
        result = get_sbp_press_releases("2026-03-31", lookback_days=7)
        # Only the March 25 release should appear (within 7 days of March 31)
        assert "maintains" in result.lower() or "12%" in result
        assert "100bps" not in result  # Jan 28 release should be filtered out

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_handles_network_error(self, mock_get):
        mock_get.side_effect = Exception("Timeout")
        result = get_sbp_press_releases("2026-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_empty_page(self, mock_get):
        mock_get.return_value = _mock_response("<html><body></body></html>")
        result = get_sbp_press_releases("2026-03-31")
        assert isinstance(result, str)
        assert "No recent" in result


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
    def test_combines_multiple_sources(self, mock_get):
        # 5 scraper calls: PSX, BR, ProPakistani, Profit, TheNews
        mock_get.side_effect = [
            _mock_response(SAMPLE_PSX_HTML),
            _mock_response(SAMPLE_BR_SEARCH_HTML),
            _mock_response(SAMPLE_PROPAKISTANI_HTML),
            _mock_response(SAMPLE_PROFIT_HTML),
            _mock_response(SAMPLE_THENEWS_HTML),
        ]
        result = get_news_psx("UBL", "2026-02-01", "2026-03-31")
        assert "PSX Announcements" in result
        assert "Business Recorder" in result
        assert "ProPakistani" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_graceful_on_total_failure(self, mock_get):
        mock_get.side_effect = Exception("Network down")
        result = get_news_psx("UBL", "2026-03-01", "2026-03-31")
        assert isinstance(result, str)

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_never_raises(self, mock_get):
        """Even with totally broken date args, should return a string."""
        mock_get.side_effect = Exception("kaboom")
        result = get_news_psx("UBL", "not-a-date", "also-not-a-date")
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
        # BR economy, Dawn, SBP
        mock_get.side_effect = [
            _mock_response(SAMPLE_BR_ECONOMY_HTML),
            _mock_response(SAMPLE_DAWN_HTML),
            _mock_response(SAMPLE_SBP_HTML),
        ]
        result = get_global_news_psx("2026-03-31")
        assert isinstance(result, str)
        assert len(result) > 100

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_includes_kse_or_sbp_content(self, mock_get):
        mock_get.side_effect = [
            _mock_response(SAMPLE_BR_ECONOMY_HTML),
            _mock_response(SAMPLE_DAWN_HTML),
            _mock_response(SAMPLE_SBP_HTML),
        ]
        result = get_global_news_psx("2026-03-31")
        lower = result.lower()
        assert any(kw in lower for kw in ["kse", "sbp", "inflation", "rate", "economy", "market"])

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_graceful_on_failure(self, mock_get):
        mock_get.side_effect = Exception("All sites down")
        result = get_global_news_psx("2026-03-31")
        assert isinstance(result, str)
        assert "No macro news" in result

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_never_raises(self, mock_get):
        """Even with broken date, should return string."""
        mock_get.side_effect = Exception("kaboom")
        result = get_global_news_psx("not-a-date")
        assert isinstance(result, str)

    @patch("tradingagents.dataflows.psx_news.requests.get")
    def test_respects_limit(self, mock_get):
        mock_get.return_value = _mock_response(SAMPLE_BR_ECONOMY_HTML)
        result = get_global_news_psx("2026-03-31", look_back_days=7, limit=1)
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
        assert "UBL" in result or "No announcements" in result
