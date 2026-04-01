"""Unit tests for PSX stock data module. No API keys or live network calls required."""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

from tradingagents.dataflows.psx_stock import (
    normalize_psx_ticker,
    is_psx_ticker,
    get_psx_stock_data,
    get_psx_indicators,
    get_psx_fundamentals,
    get_psx_balance_sheet,
    get_psx_cashflow,
    get_psx_income_statement,
    get_psx_insider_transactions,
    PSX_TICKER_LIST,
)


class TestNormalizePsxTicker(unittest.TestCase):
    def test_bare_ticker_gets_suffix(self):
        assert normalize_psx_ticker("UBL") == "UBL.KA"

    def test_already_suffixed_unchanged(self):
        assert normalize_psx_ticker("UBL.KA") == "UBL.KA"

    def test_lowercase_uppercased(self):
        assert normalize_psx_ticker("bahl") == "BAHL.KA"

    def test_lowercase_with_suffix(self):
        assert normalize_psx_ticker("hbl.ka") == "HBL.KA"


class TestIsPsxTicker(unittest.TestCase):
    def test_with_ka_suffix(self):
        assert is_psx_ticker("UBL.KA") is True

    def test_bare_kse100_ticker(self):
        assert is_psx_ticker("UBL") is True

    def test_us_ticker_not_psx(self):
        assert is_psx_ticker("AAPL") is False

    def test_case_insensitive(self):
        assert is_psx_ticker("engro") is True

    def test_unknown_ticker(self):
        assert is_psx_ticker("XXXFAKE") is False


class TestPsxTickerList(unittest.TestCase):
    def test_minimum_30_tickers(self):
        assert len(PSX_TICKER_LIST) >= 30

    def test_contains_major_tickers(self):
        for t in ["HBL", "UBL", "MCB", "ENGRO", "LUCK", "OGDC", "PPL", "TRG", "SYS"]:
            assert t in PSX_TICKER_LIST, f"{t} missing from PSX_TICKER_LIST"


class TestGetPsxStockData(unittest.TestCase):
    @patch("tradingagents.dataflows.psx_stock.get_YFin_data_online")
    def test_returns_ohlcv(self, mock_yf):
        mock_yf.return_value = (
            "# Stock data for UBL.KA from 2026-03-01 to 2026-03-31\n"
            "# Total records: 20\n\nDate,Open,High,Low,Close,Volume\n"
            "2026-03-03,150.0,155.0,149.0,153.0,100000\n"
        )
        result = get_psx_stock_data("UBL", "2026-03-01", "2026-03-31")
        mock_yf.assert_called_once_with("UBL.KA", "2026-03-01", "2026-03-31")
        assert "Close" in result
        assert "UBL.KA" in result

    @patch("tradingagents.dataflows.psx_stock.get_YFin_data_online")
    def test_normalizes_ticker(self, mock_yf):
        mock_yf.return_value = ""
        get_psx_stock_data("bahl", "2026-03-01", "2026-03-31")
        mock_yf.assert_called_once_with("BAHL.KA", "2026-03-01", "2026-03-31")


class TestGetPsxIndicators(unittest.TestCase):
    @patch("tradingagents.dataflows.psx_stock.get_stock_stats_indicators_window")
    def test_rsi(self, mock_ind):
        mock_ind.return_value = "## rsi values from 2026-03-17 to 2026-03-31:\n\n2026-03-31: 55.3\n"
        result = get_psx_indicators("UBL", "rsi", "2026-03-31", 14)
        mock_ind.assert_called_once_with("UBL.KA", "rsi", "2026-03-31", 14)
        assert "rsi" in result.lower()


class TestGetPsxFundamentals(unittest.TestCase):
    @patch("tradingagents.dataflows.psx_stock.yf_get_fundamentals")
    def test_has_pe(self, mock_fund):
        mock_fund.return_value = (
            "# Company Fundamentals for UBL.KA\n\n"
            "Name: United Bank Limited\nPE Ratio (TTM): 5.2\n"
        )
        result = get_psx_fundamentals("UBL")
        mock_fund.assert_called_once_with("UBL.KA", None)
        assert "PE Ratio" in result


class TestGetPsxBalanceSheet(unittest.TestCase):
    @patch("tradingagents.dataflows.psx_stock.yf_get_balance_sheet")
    def test_delegates_with_normalized_ticker(self, mock_bs):
        mock_bs.return_value = "# Balance Sheet data for UBL.KA (quarterly)\n\nSomeData"
        result = get_psx_balance_sheet("UBL")
        mock_bs.assert_called_once_with("UBL.KA", "quarterly", None)
        assert "Balance Sheet" in result


class TestGetPsxCashflow(unittest.TestCase):
    @patch("tradingagents.dataflows.psx_stock.yf_get_cashflow")
    def test_delegates_with_normalized_ticker(self, mock_cf):
        mock_cf.return_value = "# Cash Flow data for UBL.KA (quarterly)\n\nSomeData"
        result = get_psx_cashflow("UBL")
        mock_cf.assert_called_once_with("UBL.KA", "quarterly", None)
        assert "Cash Flow" in result


class TestGetPsxIncomeStatement(unittest.TestCase):
    @patch("tradingagents.dataflows.psx_stock.yf_get_income_statement")
    def test_delegates_with_normalized_ticker(self, mock_is):
        mock_is.return_value = "# Income Statement data for UBL.KA (quarterly)\n\nSomeData"
        result = get_psx_income_statement("UBL")
        mock_is.assert_called_once_with("UBL.KA", "quarterly", None)
        assert "Income Statement" in result


class TestGetPsxInsiderTransactions(unittest.TestCase):
    @patch("tradingagents.dataflows.psx_stock.requests.get")
    def test_scraping_success(self, mock_get):
        html = """
        <html><body>
        <table><tr><td>Director disclosure: CEO acquired 10,000 shares</td></tr></table>
        </body></html>
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = get_psx_insider_transactions("UBL")
        assert "Director" in result or "director" in result
        assert "UBL" in result

    @patch("tradingagents.dataflows.psx_stock.requests.get")
    def test_scraping_failure_graceful(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        result = get_psx_insider_transactions("UBL")
        assert isinstance(result, str)
        assert "Unable to retrieve" in result

    @patch("tradingagents.dataflows.psx_stock.requests.get")
    def test_no_disclosures_found(self, mock_get):
        html = "<html><body><p>No relevant data</p></body></html>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = get_psx_insider_transactions("OGDC")
        assert "No director/insider disclosures" in result

    @patch("tradingagents.dataflows.psx_stock.requests.get")
    def test_strips_ka_suffix_for_url(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body></body></html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        get_psx_insider_transactions("UBL.KA")
        called_url = mock_get.call_args[0][0]
        assert called_url == "https://dps.psx.com.pk/company/UBL"


class TestInterfaceWiring(unittest.TestCase):
    """Verify PSX functions are properly wired in interface.py."""

    def test_psx_in_vendor_list(self):
        from tradingagents.dataflows.interface import VENDOR_LIST
        assert "psx" in VENDOR_LIST

    def test_psx_in_vendor_methods(self):
        from tradingagents.dataflows.interface import VENDOR_METHODS
        assert "psx" in VENDOR_METHODS["get_stock_data"]
        assert "psx" in VENDOR_METHODS["get_indicators"]
        assert "psx" in VENDOR_METHODS["get_fundamentals"]
        assert "psx" in VENDOR_METHODS["get_balance_sheet"]
        assert "psx" in VENDOR_METHODS["get_cashflow"]
        assert "psx" in VENDOR_METHODS["get_income_statement"]
        assert "psx" in VENDOR_METHODS["get_insider_transactions"]


if __name__ == "__main__":
    unittest.main()
