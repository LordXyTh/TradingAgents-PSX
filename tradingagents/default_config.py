import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": "anthropic",
    "deep_think_llm": "claude-sonnet-4-6",
    "quick_think_llm": "claude-sonnet-4-6",
    "backend_url": "https://api.anthropic.com",
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
}

# PSX (Pakistan Stock Exchange) vendor config
PSX_CONFIG = {
    **DEFAULT_CONFIG,
    "data_vendors": {
        "core_stock_apis": "psx",
        "technical_indicators": "psx",
        "fundamental_data": "psx",
        "news_data": "psx",
    },
}


def get_config_for_ticker(ticker: str) -> dict:
    """
    Auto-detect market from ticker and return appropriate config.
    PSX tickers (in PSX_TICKER_LIST or ending in .KA) → PSX_CONFIG
    Everything else → DEFAULT_CONFIG
    """
    # Lazy import to avoid circular imports (psx_stock depends on dataflows)
    from tradingagents.dataflows.psx_stock import is_psx_ticker

    if is_psx_ticker(ticker):
        return PSX_CONFIG.copy()
    return DEFAULT_CONFIG.copy()
