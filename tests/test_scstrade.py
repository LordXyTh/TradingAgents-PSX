"""Tests for SCSTrade API integration — mocked POST requests, date parsing,
graceful failure on errors."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from tradingagents.dataflows.scstrade import (
    _ms_to_date,
    _parse_date_flexible,
    _in_window,
    get_scstrade_announcements,
    get_scstrade_news,
    get_scstrade_research,
    get_scstrade_insider_transactions,
)


# ---------------------------------------------------------------------------
# Sample API responses
# ---------------------------------------------------------------------------

SAMPLE_ANNOUNCEMENTS_RESPONSE = {
    "d": [
        {
            "company_code": "UBL",
            "bm_date": "/Date(1740441600000)/",  # 2025-02-25
            "bm_quarter_number": "4",
            "bm_eps_quarter": "12.50",
            "bm_eps_cum": "45.30",
            "bm_dividend": "20",
            "bm_bonus": "",
            "bm_right_per": "",
            "bm_bc_exp": "",
        },
        {
            "company_code": "UBL",
            "bm_date": "/Date(1727740800000)/",  # 2024-10-01
            "bm_quarter_number": "3",
            "bm_eps_quarter": "11.00",
            "bm_eps_cum": "32.80",
            "bm_dividend": "15",
            "bm_bonus": "5",
            "bm_right_per": "",
            "bm_bc_exp": "",
        },
    ]
}

SAMPLE_NEWS_RESPONSE = {
    "d": [
        {
            "news_date": "/Date(1742860800000)/",  # 2025-03-25
            "news_desc": "UBL declares quarterly dividend",
            "news_text": "United Bank Limited has declared a cash dividend of Rs 5 per share.",
            "newslink": "https://example.com/news/1",
        },
        {
            "news_date": "/Date(1742688000000)/",  # 2025-03-23
            "news_desc": "UBL board approves new branch expansion",
            "news_text": "",
            "newslink": "",
        },
    ]
}

SAMPLE_RESEARCH_RESPONSE = {
    "d": [
        {
            "FileTitle": "UBL - Quarterly Review Q4 2025",
            "FileDesc": "Strong earnings driven by NII growth",
            "FileVPath": "/Research/UBL_Q4_2025.pdf",
        },
        {
            "FileTitle": "Banking Sector Outlook 2026",
            "FileDesc": "Banking Sector Outlook 2026",
            "FileVPath": "https://www.scstrade.com/Research/Banking_2026.pdf",
        },
    ]
}

SAMPLE_INSIDER_HTML = """
<html><body>
<table>
  <tr><th>Category</th><th>Date</th><th>Title</th><th>Action</th></tr>
  <tr><td>Financial</td><td>25-Mar-2026</td><td>Q4 Results</td><td>View</td></tr>
</table>
<table>
  <tr><th>Date</th><th>Name</th><th>Role</th><th>Direction</th></tr>
  <tr><td>20-Mar-2026</td><td>Ahmed Khan</td><td>Director</td><td>Buy</td></tr>
  <tr><td>15-Mar-2026</td><td>Sara Ali</td><td>CEO</td><td>Sell</td></tr>
  <tr><td>01-Jan-2025</td><td>Old Person</td><td>CFO</td><td>Buy</td></tr>
</table>
</body></html>
"""


def _mock_post_response(json_data: dict, status_code: int = 200):
    """Create a mock requests.Response for POST calls."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock


def _mock_get_response(html: str, status_code: int = 200):
    """Create a mock requests.Response for GET calls."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = html
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock


# ---------------------------------------------------------------------------
# Tests: _ms_to_date
# ---------------------------------------------------------------------------

class TestMsToDate:
    def test_parses_ms_timestamp(self):
        result = _ms_to_date("/Date(1740441600000)/")
        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2025

    def test_parses_plain_number(self):
        result = _ms_to_date("1740441600000")
        assert result is not None

    def test_returns_none_for_invalid(self):
        assert _ms_to_date("not a date") is None
        assert _ms_to_date("") is None

    def test_result_has_no_tzinfo(self):
        result = _ms_to_date("/Date(1740441600000)/")
        assert result.tzinfo is None


# ---------------------------------------------------------------------------
# Tests: _parse_date_flexible
# ---------------------------------------------------------------------------

class TestParseDateFlexible:
    def test_scstrade_format(self):
        assert _parse_date_flexible("31-Mar-2026") == datetime(2026, 3, 31)

    def test_iso_format(self):
        assert _parse_date_flexible("2026-03-31") == datetime(2026, 3, 31)

    def test_dmy_short(self):
        assert _parse_date_flexible("25 Feb 2026") == datetime(2026, 2, 25)

    def test_invalid_returns_none(self):
        assert _parse_date_flexible("garbage") is None

    def test_strips_whitespace(self):
        assert _parse_date_flexible("  31-Mar-2026  ") == datetime(2026, 3, 31)


# ---------------------------------------------------------------------------
# Tests: _in_window
# ---------------------------------------------------------------------------

class TestInWindow:
    def test_within_window(self):
        curr = datetime(2026, 3, 31)
        dt = datetime(2026, 3, 15)
        assert _in_window(dt, curr, 30) is True

    def test_outside_window(self):
        curr = datetime(2026, 3, 31)
        dt = datetime(2025, 1, 1)
        assert _in_window(dt, curr, 30) is False

    def test_none_returns_false(self):
        """Unlike psx_news._in_date_window, scstrade._in_window excludes None dates."""
        curr = datetime(2026, 3, 31)
        assert _in_window(None, curr, 30) is False

    def test_edge_exact_boundary(self):
        curr = datetime(2026, 3, 31)
        dt = datetime(2026, 3, 1)
        assert _in_window(dt, curr, 30) is True


# ---------------------------------------------------------------------------
# Tests: get_scstrade_announcements
# ---------------------------------------------------------------------------

class TestGetSCStradeAnnouncements:
    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_returns_string(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_ANNOUNCEMENTS_RESPONSE)
        result = get_scstrade_announcements("UBL", "2025-03-31", lookback_days=90)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_contains_eps_data(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_ANNOUNCEMENTS_RESPONSE)
        result = get_scstrade_announcements("UBL", "2025-03-31", lookback_days=90)
        assert "EPS" in result
        assert "12.50" in result or "45.30" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_contains_dividend_data(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_ANNOUNCEMENTS_RESPONSE)
        result = get_scstrade_announcements("UBL", "2025-03-31", lookback_days=90)
        assert "Div=" in result or "dividend" in result.lower()

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_filters_by_date(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_ANNOUNCEMENTS_RESPONSE)
        # Only look back 30 days from 2025-03-31 — should include Feb 25 entry
        result = get_scstrade_announcements("UBL", "2025-03-31", lookback_days=40)
        assert "UBL" in result
        # Oct 2024 entry should be filtered out
        assert "Q3" not in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_strips_ka_suffix(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_ANNOUNCEMENTS_RESPONSE)
        get_scstrade_announcements("UBL.KA", "2025-03-31")
        payload = mock_post.call_args[1]["json"]
        assert payload["par"] == "UBL"

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_empty_response(self, mock_post):
        mock_post.return_value = _mock_post_response({"d": []})
        result = get_scstrade_announcements("UBL", "2025-03-31")
        assert "No board meeting data" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_graceful_on_500(self, mock_post):
        mock_post.return_value = _mock_post_response({}, status_code=500)
        result = get_scstrade_announcements("UBL", "2025-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_graceful_on_connection_error(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")
        result = get_scstrade_announcements("UBL", "2025-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_posts_to_correct_url(self, mock_post):
        mock_post.return_value = _mock_post_response({"d": []})
        get_scstrade_announcements("UBL", "2025-03-31")
        called_url = mock_post.call_args[0][0]
        assert "SS_CompanySnapShotAnn" in called_url
        assert "chartact" in called_url


# ---------------------------------------------------------------------------
# Tests: get_scstrade_news
# ---------------------------------------------------------------------------

class TestGetSCStradeNews:
    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_returns_string(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_NEWS_RESPONSE)
        result = get_scstrade_news("UBL", "2025-03-31", lookback_days=30)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_contains_news_text(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_NEWS_RESPONSE)
        result = get_scstrade_news("UBL", "2025-03-31", lookback_days=30)
        assert "dividend" in result.lower()

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_includes_link(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_NEWS_RESPONSE)
        result = get_scstrade_news("UBL", "2025-03-31", lookback_days=30)
        assert "example.com" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_uses_symbol_payload(self, mock_post):
        mock_post.return_value = _mock_post_response({"d": []})
        get_scstrade_news("BAHL", "2025-03-31")
        payload = mock_post.call_args[1]["json"]
        assert payload["symbol"] == "BAHL"

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_empty_response(self, mock_post):
        mock_post.return_value = _mock_post_response({"d": []})
        result = get_scstrade_news("UBL", "2025-03-31")
        assert "No news found" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_graceful_on_500(self, mock_post):
        mock_post.return_value = _mock_post_response({}, status_code=500)
        result = get_scstrade_news("UBL", "2025-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_graceful_on_timeout(self, mock_post):
        mock_post.side_effect = Exception("Read timed out")
        result = get_scstrade_news("UBL", "2025-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_posts_to_correct_url(self, mock_post):
        mock_post.return_value = _mock_post_response({"d": []})
        get_scstrade_news("UBL", "2025-03-31")
        called_url = mock_post.call_args[0][0]
        assert "SS_CompanySnapShotNews" in called_url


# ---------------------------------------------------------------------------
# Tests: get_scstrade_research
# ---------------------------------------------------------------------------

class TestGetSCStradeResearch:
    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_returns_string(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_RESEARCH_RESPONSE)
        result = get_scstrade_research("UBL")
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_contains_report_titles(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_RESEARCH_RESPONSE)
        result = get_scstrade_research("UBL")
        assert "Quarterly Review" in result
        assert "Banking Sector" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_contains_pdf_urls(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_RESEARCH_RESPONSE)
        result = get_scstrade_research("UBL")
        assert "PDF:" in result
        assert ".pdf" in result.lower()

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_relative_path_gets_base_url(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_RESEARCH_RESPONSE)
        result = get_scstrade_research("UBL")
        assert "https://www.scstrade.com/Research/UBL_Q4_2025.pdf" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_absolute_url_preserved(self, mock_post):
        mock_post.return_value = _mock_post_response(SAMPLE_RESEARCH_RESPONSE)
        result = get_scstrade_research("UBL")
        assert "https://www.scstrade.com/Research/Banking_2026.pdf" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_empty_response(self, mock_post):
        mock_post.return_value = _mock_post_response({"d": []})
        result = get_scstrade_research("UBL")
        assert "No research reports" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_graceful_on_500(self, mock_post):
        mock_post.return_value = _mock_post_response({}, status_code=500)
        result = get_scstrade_research("UBL")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_graceful_on_connection_error(self, mock_post):
        mock_post.side_effect = Exception("Connection refused")
        result = get_scstrade_research("UBL")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_strips_ka_suffix(self, mock_post):
        mock_post.return_value = _mock_post_response({"d": []})
        get_scstrade_research("UBL.KA")
        payload = mock_post.call_args[1]["json"]
        assert payload["par"] == "UBL"


# ---------------------------------------------------------------------------
# Tests: get_scstrade_insider_transactions
# ---------------------------------------------------------------------------

class TestGetSCStradeInsiderTransactions:
    @patch("tradingagents.dataflows.scstrade.requests.get")
    def test_returns_string(self, mock_get):
        mock_get.return_value = _mock_get_response(SAMPLE_INSIDER_HTML)
        result = get_scstrade_insider_transactions("UBL", "2026-03-31", lookback_days=30)
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("tradingagents.dataflows.scstrade.requests.get")
    def test_extracts_buy_sell(self, mock_get):
        mock_get.return_value = _mock_get_response(SAMPLE_INSIDER_HTML)
        result = get_scstrade_insider_transactions("UBL", "2026-03-31", lookback_days=30)
        assert "Buy" in result
        assert "Sell" in result

    @patch("tradingagents.dataflows.scstrade.requests.get")
    def test_extracts_names_and_roles(self, mock_get):
        mock_get.return_value = _mock_get_response(SAMPLE_INSIDER_HTML)
        result = get_scstrade_insider_transactions("UBL", "2026-03-31", lookback_days=30)
        assert "Ahmed Khan" in result
        assert "Director" in result
        assert "Sara Ali" in result

    @patch("tradingagents.dataflows.scstrade.requests.get")
    def test_filters_by_date(self, mock_get):
        mock_get.return_value = _mock_get_response(SAMPLE_INSIDER_HTML)
        result = get_scstrade_insider_transactions("UBL", "2026-03-31", lookback_days=30)
        # Jan 2025 entry should be filtered out
        assert "Old Person" not in result

    @patch("tradingagents.dataflows.scstrade.requests.get")
    def test_strips_ka_suffix(self, mock_get):
        mock_get.return_value = _mock_get_response(SAMPLE_INSIDER_HTML)
        get_scstrade_insider_transactions("UBL.KA", "2026-03-31")
        called_url = mock_get.call_args[0][0]
        assert "symbol=UBL" in called_url
        assert ".KA" not in called_url

    @patch("tradingagents.dataflows.scstrade.requests.get")
    def test_empty_html(self, mock_get):
        mock_get.return_value = _mock_get_response("<html><body></body></html>")
        result = get_scstrade_insider_transactions("UBL", "2026-03-31")
        assert "No insider transactions" in result

    @patch("tradingagents.dataflows.scstrade.requests.get")
    def test_graceful_on_500(self, mock_get):
        mock_get.return_value = _mock_get_response("", status_code=500)
        result = get_scstrade_insider_transactions("UBL", "2026-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.scstrade.requests.get")
    def test_graceful_on_connection_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        result = get_scstrade_insider_transactions("UBL", "2026-03-31")
        assert isinstance(result, str)
        assert "Could not fetch" in result

    @patch("tradingagents.dataflows.scstrade.requests.get")
    def test_uses_correct_url(self, mock_get):
        mock_get.return_value = _mock_get_response("<html><body></body></html>")
        get_scstrade_insider_transactions("BAHL", "2026-03-31")
        called_url = mock_get.call_args[0][0]
        assert "SS_CompanySnapShot" in called_url
        assert "symbol=BAHL" in called_url


# ---------------------------------------------------------------------------
# Tests: never raises guarantee
# ---------------------------------------------------------------------------

class TestNeverRaises:
    """All functions must return strings, never raise exceptions."""

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_announcements_never_raises(self, mock_post):
        mock_post.side_effect = Exception("kaboom")
        result = get_scstrade_announcements("UBL", "bad-date")
        assert isinstance(result, str)

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_news_never_raises(self, mock_post):
        mock_post.side_effect = Exception("kaboom")
        result = get_scstrade_news("UBL", "bad-date")
        assert isinstance(result, str)

    @patch("tradingagents.dataflows.scstrade.requests.post")
    def test_research_never_raises(self, mock_post):
        mock_post.side_effect = Exception("kaboom")
        result = get_scstrade_research("UBL")
        assert isinstance(result, str)

    @patch("tradingagents.dataflows.scstrade.requests.get")
    def test_insider_never_raises(self, mock_get):
        mock_get.side_effect = Exception("kaboom")
        result = get_scstrade_insider_transactions("UBL", "bad-date")
        assert isinstance(result, str)
