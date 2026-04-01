from langchain_core.messages import HumanMessage, RemoveMessage, AIMessage
import traceback
import time

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Only applied to user-facing agents (analysts, portfolio manager).
    Internal debate agents stay in English for reasoning quality.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )

def resilient_node(node_fn, node_name: str, fallback_state: dict):
    """Wrap an agent node function to catch errors and return fallback state.
    
    Instead of crashing the entire graph on a transient error (rate limit,
    network hiccup, etc.), log the error and continue with a degraded result.
    The downstream agents will see an empty/error report but the run completes.
    """
    def wrapper(state):
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                return node_fn(state)
            except Exception as e:
                err_str = str(e)
                is_rate_limit = any(x in err_str.lower() for x in ["rate limit", "429", "too many", "quota"])
                is_transient = any(x in err_str.lower() for x in ["timeout", "connection", "503", "502", "overloaded"])

                if (is_rate_limit or is_transient) and attempt < max_attempts:
                    wait = 30 * attempt  # 30s, 60s backoff
                    print(f"\n[{node_name}] {type(e).__name__} on attempt {attempt}/{max_attempts}. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                # Non-retryable or exhausted retries — return degraded fallback
                print(f"\n[{node_name}] Failed after {attempt} attempt(s): {type(e).__name__}: {err_str[:200]}")
                result = fallback_state.copy()
                result["messages"] = [AIMessage(content=f"[{node_name} unavailable: {type(e).__name__}]")]
                return result
        return fallback_state  # Should never reach here
    return wrapper


def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
