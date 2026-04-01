"""SCSTrade JSON API integration — announcements, news, research reports,
and insider transactions for PSX-listed companies."""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

_REQUEST_TIMEOUT = 8
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}
_JSON_HEADERS = {
    **_HEADERS,
    "Content-Type": "application/json; charset=utf-8",
}

# Date patterns common on SCSTrade HTML pages
_DATE_FORMATS = [
    "%d-%b-%Y",  # 31-Mar-2026
    "%d %b %Y",
    "%Y-%m-%d",
]


def _ms_to_date(ms_str: str) -> datetime | None:
    """Convert '/Date(1771959600000)/' style timestamp to datetime."""
    m = re.search(r"\d+", str(ms_str))
    if not m:
        return None
    return datetime.fromtimestamp(int(m.group()) / 1000, tz=timezone.utc).replace(
        tzinfo=None
    )


def _parse_date_flexible(date_str: str) -> datetime | None:
    """Try multiple date formats common on SCSTrade pages."""
    date_str = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _in_window(dt: datetime | None, curr_dt: datetime, lookback_days: int) -> bool:
    """Return True if dt falls within [curr_dt - lookback_days, curr_dt]."""
    if dt is None:
        return False
    start = curr_dt - timedelta(days=lookback_days)
    return start <= dt <= curr_dt


def _post_json(url: str, payload: dict) -> dict:
    """POST JSON to SCSTrade API endpoint. Returns parsed response dict."""
    resp = requests.post(
        url, json=payload, headers=_JSON_HEADERS, timeout=_REQUEST_TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Announcements API (board meeting results)
# ---------------------------------------------------------------------------


def get_scstrade_announcements(
    ticker: str, curr_date: str, lookback_days: int = 90
) -> str:
    """Board meeting results: EPS, dividends, bonuses from SCSTrade API."""
    try:
        bare = ticker.upper().replace(".KA", "")
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

        url = "https://www.scstrade.com/stockscreening/SS_CompanySnapShotAnn.aspx/chartact"
        data = _post_json(url, {"par": bare})

        rows = data.get("d", [])
        if not rows:
            return f"[SCSTrade Announcements] No board meeting data found for {bare}."

        items = []
        for row in rows:
            date_val = _ms_to_date(row.get("bm_date", ""))
            if not _in_window(date_val, curr_dt, lookback_days):
                continue

            date_str = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
            code = row.get("company_code", bare)
            quarter = row.get("bm_quarter_number", "")
            eps_q = row.get("bm_eps_quarter", "")
            eps_cum = row.get("bm_eps_cum", "")
            dividend = row.get("bm_dividend", "")
            bonus = row.get("bm_bonus", "")
            right = row.get("bm_right_per", "")

            parts = [f"[{date_str}] {code}"]
            if quarter:
                parts.append(f"Q{quarter}")
            if eps_q:
                parts.append(f"EPS(Q)={eps_q}")
            if eps_cum:
                parts.append(f"EPS(Cum)={eps_cum}")
            if dividend:
                parts.append(f"Div={dividend}%")
            if bonus:
                parts.append(f"Bonus={bonus}%")
            if right:
                parts.append(f"Right={right}%")

            items.append("- " + " | ".join(parts))

        if not items:
            return f"[SCSTrade Announcements] No board meeting results for {bare} in last {lookback_days} days."

        header = f"## SCSTrade Board Meeting Results for {bare} (last {lookback_days} days from {curr_date}):\n\n"
        return header + "\n".join(items)
    except Exception as e:
        return f"[SCSTrade Announcements] Could not fetch data for {ticker}: {e}"


# ---------------------------------------------------------------------------
# News / Research Notes API
# ---------------------------------------------------------------------------


def get_scstrade_news(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """Company news snippets from SCSTrade news feed API."""
    try:
        bare = ticker.upper().replace(".KA", "")
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

        url = "https://www.scstrade.com/stockscreening/SS_CompanySnapShotNews.aspx/chart"
        data = _post_json(url, {"symbol": bare})

        rows = data.get("d", [])
        if not rows:
            return f"[SCSTrade News] No news found for {bare}."

        items = []
        for row in rows:
            date_val = _ms_to_date(row.get("news_date", ""))
            if not _in_window(date_val, curr_dt, lookback_days):
                continue

            date_str = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
            desc = (row.get("news_desc") or "").strip()
            text = (row.get("news_text") or "").strip()
            link = (row.get("newslink") or "").strip()

            title = desc or text[:120]
            if not title:
                continue

            entry = f"- [{date_str}] {title}"
            if text and text != desc:
                entry += f"\n  {text[:200]}"
            if link:
                entry += f"\n  Link: {link}"
            items.append(entry)

        if not items:
            return f"[SCSTrade News] No news for {bare} in last {lookback_days} days."

        header = f"## SCSTrade News for {bare} (last {lookback_days} days from {curr_date}):\n\n"
        return header + "\n".join(items[:30])
    except Exception as e:
        return f"[SCSTrade News] Could not fetch news for {ticker}: {e}"


# ---------------------------------------------------------------------------
# Research Reports API
# ---------------------------------------------------------------------------


def get_scstrade_research(ticker: str) -> str:
    """List research report titles + PDF URLs from SCSTrade. No date filter."""
    try:
        bare = ticker.upper().replace(".KA", "")

        url = "https://www.scstrade.com/stockscreening/SS_ResearchReports.aspx/chart"
        data = _post_json(url, {"par": bare})

        rows = data.get("d", [])
        if not rows:
            return f"[SCSTrade Research] No research reports found for {bare}."

        items = []
        for row in rows:
            title = (row.get("FileTitle") or "").strip()
            desc = (row.get("FileDesc") or "").strip()
            vpath = (row.get("FileVPath") or "").strip()

            if not title and not desc:
                continue

            pdf_url = ""
            if vpath:
                if vpath.startswith("http"):
                    pdf_url = vpath
                else:
                    pdf_url = f"https://www.scstrade.com{vpath}"

            entry = f"- {title or desc}"
            if desc and desc != title:
                entry += f"\n  {desc}"
            if pdf_url:
                entry += f"\n  PDF: {pdf_url}"
            items.append(entry)

        if not items:
            return f"[SCSTrade Research] No research reports for {bare}."

        header = f"## SCSTrade Research Reports for {bare}:\n\n"
        return header + "\n".join(items[:20])
    except Exception as e:
        return f"[SCSTrade Research] Could not fetch reports for {ticker}: {e}"


# ---------------------------------------------------------------------------
# Insider Transactions (HTML scrape from snapshot page)
# ---------------------------------------------------------------------------


def get_scstrade_insider_transactions(
    ticker: str, curr_date: str, lookback_days: int = 30
) -> str:
    """Insider buy/sell from SCSTrade HTML table. High signal for sentiment."""
    try:
        bare = ticker.upper().replace(".KA", "")
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

        url = f"https://scstrade.com/stockscreening/SS_CompanySnapShot.aspx?symbol={bare}"
        resp = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")

        # Table 1 (second table): insider transactions
        # cols: [Date, Name, Role, Direction(Buy/Sell)]
        insiders = []
        if len(tables) > 1:
            for row in tables[1].find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                date_text = cells[0].get_text(strip=True)
                name = cells[1].get_text(strip=True)
                role = cells[2].get_text(strip=True)
                direction = cells[3].get_text(strip=True)

                date_val = _parse_date_flexible(date_text)
                if not name or not direction:
                    continue
                if not _in_window(date_val, curr_dt, lookback_days):
                    continue

                date_display = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
                insiders.append(
                    f"- [{date_display}] {name} ({role}): {direction}"
                )

        if not insiders:
            return f"[SCSTrade Insiders] No insider transactions found for {bare} in last {lookback_days} days."

        header = f"## SCSTrade Insider Transactions for {bare} (last {lookback_days} days from {curr_date}):\n\n"
        return header + "\n".join(insiders[:30])
    except Exception as e:
        return f"[SCSTrade Insiders] Could not fetch insider data for {ticker}: {e}"
