"""PSX (Pakistan Stock Exchange) stock data via yfinance with .KA ticker normalization."""

from typing import Annotated
from datetime import datetime

from .scstrade import get_scstrade_insider_transactions
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as yf_get_fundamentals,
    get_balance_sheet as yf_get_balance_sheet,
    get_cashflow as yf_get_cashflow,
    get_income_statement as yf_get_income_statement,
)

# Full KSE-100 Index constituents (as of March 2025 recomposition)
# Source: ksestocks.com/MarketIndexes/KSE-100
PSX_TICKER_LIST = [
    # Power Generation & Distribution (4)
    "KEL", "HUBC", "KAPCO", "SPWL",
    # Oil & Gas Exploration (4)
    "OGDC", "PPL", "POL", "MARI",
    # Commercial Banks (13)
    "SCBPL", "BOP", "NBP", "MEBL", "BAFL", "FABL", "HBL", "AKBL",
    "UBL", "MCB", "ABL", "BAHL", "HMB",
    # Technology & Communication (3)
    "PTC", "TRG", "SYS",
    # Cement (7)
    "FCCL", "MLCF", "DGKC", "LUCK", "PIOC", "KOHC", "CHCC",
    # Real Estate Investment Trust (1)
    "DCR",
    # Fertilizer (5)
    "FATIMA", "EFERT", "FFBL", "FFC", "ENGRO",
    # Transport (1)
    "PIBTL",
    # Chemical (4)
    "LOTCHEM", "EPCL", "COLG", "ARPL",
    # Food & Personal Care (4)
    "UNITY", "NATF", "NESTLE", "MUREB",
    # Oil & Gas Marketing (6)
    "HASCOL", "SSGC", "SNGP", "PSO", "SHEL", "APL",
    # Textile Composite (7)
    "ILP", "GATM", "ANL", "FML", "NML", "KTML", "NCL",
    # Cable & Electrical (1)
    "PAEL",
    # Glass & Ceramics (1)
    "GHGL",
    # Investment Banks/Securities (2)
    "PSX", "OLPL",
    # Engineering (2)
    "ISL", "INIL",
    # Pharmaceuticals (5)
    "SEARL", "GLAXO", "AGP", "ABOT", "HINOON",
    # Insurance (3)
    "AICL", "EFUG", "JLICL",
    # Synthetic & Rayon (1)
    "IBFL",
    # Close-End Mutual Fund (1)
    "HGFA",
    # Tobacco (2)
    "PAKT", "PMPK",
    # Modarabas (1)
    "FHAM",
    # Automobile Assembler (5)
    "HCAR", "MTL", "ATLH", "PSMC", "INDU",
    # Refinery (1)
    "ATRL",
    # Textile Weaving (1)
    "YOUW",
    # Paper & Board (1)
    "PKGS",
    # Automobile Parts (2)
    "THALL", "AGIL",
    # Miscellaneous (2)
    "SHFA", "PSEL",
    # Sugar (1)
    "JDWS",
    # Textile Spinning (1)
    "IDYM",
    # Leather (1)
    "SRVI",
    # Woollen (1)
    "BNWM",
]


def normalize_psx_ticker(symbol: str) -> str:
    """Append .KA suffix if not already present."""
    clean = symbol.upper().replace(".__US__", "")
    if not clean.endswith(".KA"):
        return f"{clean}.KA"
    return clean


def is_psx_ticker(symbol: str) -> bool:
    """
    Detect if a ticker should use PSX data stack.
    
    Routing rules (in order of precedence):
    1. Explicit .KA suffix → PSX (e.g., UBL.KA)
    2. Explicit US suffix (.N, .O, .A, .K) → NOT PSX (force US)
    3. No suffix + in PSX_TICKER_LIST → PSX (convenience for known tickers)
    4. No suffix + NOT in list → NOT PSX (default to yfinance/US)
    
    To force US market for a ticker that's also in PSX list, use explicit suffix.
    """
    upper = symbol.upper()
    
    # Explicit PSX suffix → definitely PSX
    if upper.endswith(".KA"):
        return True
    
    # Explicit US/other market suffixes → NOT PSX
    # .N = NYSE, .O = NASDAQ, .A = NYSE AMEX, .K = NYSE Arca, .TO = Toronto, .L = London
    us_suffixes = ('.N', '.O', '.A', '.K', '.TO', '.L', '.T', '.HK', '.SS', '.SZ')
    for suffix in us_suffixes:
        if upper.endswith(suffix):
            return False
    
    # User explicitly chose US market (CLI appends .__US__ sentinel)
    if upper.endswith(".__US__"):
        return False

    # No suffix → check if in known PSX list
    # This is a convenience: typing "UBL" routes to PSX, "AAPL" routes to US
    return upper in PSX_TICKER_LIST


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
    PSX insider/director transactions from SCSTrade snapshot page.
    Delegates to scstrade.get_scstrade_insider_transactions.
    """
    curr_date = datetime.now().strftime("%Y-%m-%d")
    return get_scstrade_insider_transactions(ticker, curr_date, lookback_days=90)
