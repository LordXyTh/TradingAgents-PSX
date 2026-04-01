"""PSX (Pakistan Stock Exchange) stock data via yfinance with .KA ticker normalization."""

from typing import Annotated
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as yf_get_fundamentals,
    get_balance_sheet as yf_get_balance_sheet,
    get_cashflow as yf_get_cashflow,
    get_income_statement as yf_get_income_statement,
)

# Top 30+ KSE-100 tickers (bare symbols, no .KA suffix)
PSX_TICKER_LIST = [
    "OGDC", "PPL", "SUI", "SSGC", "SNGP",          # Oil & Gas / Utilities
    "HBL", "UBL", "MCB", "BAHL", "NBP",              # Banks
    "ABL", "MEBL", "BAFL", "BOP", "AKBL",            # Banks (cont.)
    "ENGRO", "EFERT", "FFC", "FFBL",                  # Fertilizer / Chemicals
    "LUCK", "DGKC", "MLCF", "PIOC", "FCCL",          # Cement
    "PSO", "SHEL", "APL", "HASCOL",                   # Oil Marketing
    "HUBC", "KEL", "KAPCO",                           # Power
    "TRG", "SYS", "AVN",                              # Technology
    "MTL", "ISL", "COLG", "NESTLE", "UNITY",          # Consumer / Misc
    "MARI", "POL", "ATRL",                            # E&P / Refinery
]


def normalize_psx_ticker(symbol: str) -> str:
    """Append .KA suffix if not already present."""
    if not symbol.upper().endswith(".KA"):
        return f"{symbol.upper()}.KA"
    return symbol.upper()


def is_psx_ticker(symbol: str) -> bool:
    """Detect if a ticker is PSX-listed."""
    upper = symbol.upper()
    return upper.endswith(".KA") or upper in PSX_TICKER_LIST


def get_psx_stock_data(
    symbol: Annotated[str, "ticker symbol of the PSX company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
):
    """OHLCV data for PSX tickers via yfinance with .KA normalization."""
    return get_YFin_data_online(normalize_psx_ticker(symbol), start_date, end_date)


def get_psx_indicators(
    symbol: Annotated[str, "ticker symbol of the PSX company"],
    indicator: Annotated[str, "technical indicator"],
    curr_date: Annotated[str, "current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    """Technical indicators for PSX via stockstats with .KA normalization."""
    return get_stock_stats_indicators_window(
        normalize_psx_ticker(symbol), indicator, curr_date, look_back_days
    )


def get_psx_fundamentals(
    ticker: Annotated[str, "ticker symbol of the PSX company"],
    curr_date: Annotated[str, "current date (not used)"] = None,
):
    """Fundamentals from yfinance (.KA)."""
    return yf_get_fundamentals(normalize_psx_ticker(ticker), curr_date)


def get_psx_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the PSX company"],
    freq: Annotated[str, "'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
):
    """Balance sheet via yfinance .KA."""
    return yf_get_balance_sheet(normalize_psx_ticker(ticker), freq, curr_date)


def get_psx_cashflow(
    ticker: Annotated[str, "ticker symbol of the PSX company"],
    freq: Annotated[str, "'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
):
    """Cash flow via yfinance .KA."""
    return yf_get_cashflow(normalize_psx_ticker(ticker), freq, curr_date)


def get_psx_income_statement(
    ticker: Annotated[str, "ticker symbol of the PSX company"],
    freq: Annotated[str, "'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
):
    """Income statement via yfinance .KA."""
    return yf_get_income_statement(normalize_psx_ticker(ticker), freq, curr_date)


def get_psx_insider_transactions(
    ticker: Annotated[str, "ticker symbol of the PSX company"],
) -> str:
    """
    PSX insider/director disclosures scraped from dps.psx.com.pk.
    Falls back gracefully if scraping fails.
    """
    bare = ticker.upper().replace(".KA", "")
    url = f"https://dps.psx.com.pk/company/{bare}"

    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for announcement/disclosure rows mentioning director or insider keywords
        disclosures = []
        keywords = ["director", "disclosure", "insider", "share", "acquisition", "disposal"]

        for row in soup.select("table tr, .announcement, .ann-item, li"):
            text = row.get_text(separator=" ", strip=True)
            if any(kw in text.lower() for kw in keywords):
                disclosures.append(text)

        if not disclosures:
            return (
                f"# Insider Transactions for {bare} (PSX)\n"
                f"No director/insider disclosures found on dps.psx.com.pk.\n"
                f"This data may not be available for all PSX tickers."
            )

        header = (
            f"# Insider / Director Disclosures for {bare} (PSX)\n"
            f"# Source: dps.psx.com.pk/company/{bare}\n"
            f"# Scraped on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        return header + "\n".join(disclosures[:50])

    except Exception as e:
        return (
            f"# Insider Transactions for {bare} (PSX)\n"
            f"Unable to retrieve insider disclosures: {e}\n"
            f"dps.psx.com.pk may be temporarily unavailable."
        )
