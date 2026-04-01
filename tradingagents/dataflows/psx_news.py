"""PSX news scraping — Business Recorder, Dawn Business, PSX announcements,
ProPakistani, Profit by Pakistan Today, The News, SBP press releases,
and SCSTrade APIs (announcements, news, research)."""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from .scstrade import (
    get_scstrade_announcements,
    get_scstrade_news as _scstrade_news,
    get_scstrade_research,
)

# Top 30+ KSE-100 companies mapped to search-friendly names
PSX_COMPANY_NAMES = {
    "OGDC": "Oil and Gas Development Company",
    "PPL": "Pakistan Petroleum",
    "PSO": "Pakistan State Oil",
    "SNGP": "Sui Northern Gas",
    "SSGC": "Sui Southern Gas",
    "HBL": "Habib Bank",
    "UBL": "United Bank",
    "MCB": "MCB Bank",
    "BAHL": "Bank AL Habib",
    "NBP": "National Bank of Pakistan",
    "ABL": "Allied Bank",
    "MEBL": "Meezan Bank",
    "BAFL": "Bank Alfalah",
    "BOP": "Bank of Punjab",
    "FABL": "Faysal Bank",
    "ENGRO": "Engro Corporation",
    "EFERT": "Engro Fertilizers",
    "FFC": "Fauji Fertilizer",
    "LUCK": "Lucky Cement",
    "DGKC": "DG Khan Cement",
    "MLCF": "Maple Leaf Cement",
    "FCCL": "Fauji Cement",
    "HUBC": "Hub Power",
    "KAPCO": "Kot Addu Power",
    "KEL": "K-Electric",
    "TRG": "TRG Pakistan",
    "SYS": "Systems Limited",
    "MARI": "Mari Petroleum",
    "POL": "Pakistan Oilfields",
    "COLG": "Colgate Palmolive Pakistan",
    "NESTLE": "Nestle Pakistan",
    "MTL": "Millat Tractors",
    "ATRL": "Attock Refinery",
    "NRL": "National Refinery",
    "ISL": "Islamabad Stock Exchange",  # placeholder
    "SEARL": "Searle Company",
    "ICI": "ICI Pakistan",
    "ABOT": "Abbott Laboratories Pakistan",
    "INDU": "Indus Motor",
    "PSMC": "Pak Suzuki Motor",
    "HCAR": "Honda Atlas Cars",
}

_REQUEST_TIMEOUT = 8
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Patterns that indicate a table row is profile info, not an announcement
_SKIP_PATTERNS = re.compile(
    r"^(CEO|Chairperson|Chairman|Secretary|Director|CFO|Company Secretary|Auditor)\b",
    re.IGNORECASE,
)


def _parse_date_flexible(date_str: str) -> datetime | None:
    """Try multiple date formats common on Pakistani news sites."""
    formats = [
        "%d %b %Y",      # 25 Feb 2026
        "%b %d, %Y",     # Feb 25, 2026
        "%Y-%m-%d",      # 2026-02-25
        "%d-%m-%Y",      # 25-02-2026
        "%d/%m/%Y",      # 25/02/2026
        "%B %d, %Y",     # February 25, 2026
        "%d %B %Y",      # 25 February 2026
        "%d %b, %Y",     # 25 Feb, 2026
        "%d-%b-%Y",      # 26-Mar-2026 (SCSTrade format)
    ]
    date_str = date_str.strip()
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _in_date_window(dt: datetime | None, curr_dt: datetime, lookback_days: int) -> bool:
    """Return True if dt falls within [curr_dt - lookback_days, curr_dt]."""
    if dt is None:
        return True  # include items with unparseable dates
    start = curr_dt - timedelta(days=lookback_days)
    return start <= dt <= curr_dt


def _strip_trailing_junk(text: str) -> str:
    """Remove trailing 'ViewPDF', 'View' etc. from announcement text."""
    return re.sub(r"\s*(ViewPDF|View)\s*$", "", text).strip()


def _fetch(url: str) -> requests.Response:
    """GET with standard timeout/headers. Caller must handle exceptions."""
    return requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)


# ---------------------------------------------------------------------------
# Individual source scrapers
# ---------------------------------------------------------------------------


def get_psx_announcements(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """Scrape PSX official announcements for a ticker from dps.psx.com.pk."""
    try:
        ticker = ticker.upper().replace(".KA", "")
        url = f"https://dps.psx.com.pk/company/{ticker}"
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

        resp = _fetch(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        announcements = []

        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                texts = [c.get_text(strip=True) for c in cells]

                date_val = None
                desc_parts = []
                for text in texts:
                    parsed = _parse_date_flexible(text)
                    if parsed and not date_val:
                        date_val = parsed
                    elif text:
                        desc_parts.append(text)

                desc = _strip_trailing_junk(" — ".join(desc_parts) if desc_parts else " | ".join(texts))
                if not desc.strip():
                    continue
                # Skip profile/management rows
                if _SKIP_PATTERNS.match(desc):
                    continue
                # Only include items that have a real parsed date
                if date_val is None:
                    continue
                if _in_date_window(date_val, curr_dt, lookback_days):
                    date_display = date_val.strftime("%Y-%m-%d")
                    announcements.append(f"- [{date_display}] {desc}")

        # Also look for announcement divs / list items
        for div in soup.find_all(["div", "li", "a"], class_=lambda c: c and "announce" in str(c).lower()):
            text = _strip_trailing_junk(div.get_text(strip=True))
            if text and len(text) > 10 and not _SKIP_PATTERNS.match(text):
                announcements.append(f"- {text}")

        if not announcements:
            return f"[PSX Announcements] No announcements found for {ticker} within the last {lookback_days} days."

        header = f"## PSX Announcements for {ticker} (last {lookback_days} days from {curr_date}):\n\n"
        return header + "\n".join(announcements[:50])
    except Exception as e:
        return f"[PSX Announcements] Could not fetch announcements for {ticker}: {e}"


def get_psx_news_brecorder(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """Scrape Business Recorder for company news."""
    try:
        ticker_upper = ticker.upper().replace(".KA", "")
        company_name = PSX_COMPANY_NAMES.get(ticker_upper, ticker_upper)
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

        search_query = company_name.replace(" ", "+")
        url = f"https://www.brecorder.com/search/{search_query}"

        resp = _fetch(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []

        for item in soup.find_all("article"):
            title_tag = item.find(["h2", "h3", "h4", "a"])
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title:
                continue

            link = ""
            a_tag = item.find("a", href=True)
            if a_tag:
                href = a_tag["href"]
                link = href if href.startswith("http") else f"https://www.brecorder.com{href}"

            date_tag = item.find("span", class_=lambda c: c and "date" in str(c).lower())
            if not date_tag:
                date_tag = item.find("time")
            date_text = date_tag.get_text(strip=True) if date_tag else ""
            date_val = _parse_date_flexible(date_text) if date_text else None

            snippet_tag = item.find("p")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

            if _in_date_window(date_val, curr_dt, lookback_days):
                date_display = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
                entry = f"### {title} ({date_display})\n"
                if snippet:
                    entry += f"{snippet}\n"
                if link:
                    entry += f"Link: {link}\n"
                articles.append(entry)

        # Fallback: story-list / search-result divs
        if not articles:
            for item in soup.find_all("div", class_=lambda c: c and ("story" in str(c).lower() or "search" in str(c).lower())):
                title_tag = item.find(["h2", "h3", "h4", "a"])
                title = title_tag.get_text(strip=True) if title_tag else ""
                if not title or len(title) < 10:
                    continue

                link = ""
                a_tag = item.find("a", href=True)
                if a_tag:
                    href = a_tag["href"]
                    link = href if href.startswith("http") else f"https://www.brecorder.com{href}"

                date_tag = item.find("span", class_=lambda c: c and "date" in str(c).lower())
                if not date_tag:
                    date_tag = item.find("time")
                date_text = date_tag.get_text(strip=True) if date_tag else ""
                date_val = _parse_date_flexible(date_text) if date_text else None

                snippet_tag = item.find("p")
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                if _in_date_window(date_val, curr_dt, lookback_days):
                    date_display = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
                    entry = f"### {title} ({date_display})\n"
                    if snippet:
                        entry += f"{snippet}\n"
                    if link:
                        entry += f"Link: {link}\n"
                    articles.append(entry)

        if not articles:
            return f"[Business Recorder] No recent news found for {ticker_upper} ({company_name})."

        header = f"## Business Recorder News for {ticker_upper} (last {lookback_days} days from {curr_date}):\n\n"
        return header + "\n".join(articles[:20])
    except Exception as e:
        return f"[Business Recorder] Could not fetch news for {ticker.upper().replace('.KA', '')}: {e}"


def get_psx_news_propakistani(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """Scrape ProPakistani for company news."""
    try:
        ticker_upper = ticker.upper().replace(".KA", "")
        company_name = PSX_COMPANY_NAMES.get(ticker_upper, ticker_upper)
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

        url = f"https://propakistani.pk/search/?q={quote_plus(company_name)}"
        resp = _fetch(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []

        for item in soup.find_all(["article", "div"], class_=lambda c: c and ("post" in str(c).lower() or "search" in str(c).lower())):
            title_tag = item.find(["h2", "h3", "h4"], class_=lambda c: c and "title" in str(c).lower()) or item.find(["h2", "h3", "h4"])
            if not title_tag:
                a_tag = item.find("a")
                title_tag = a_tag
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title or len(title) < 10:
                continue

            link = ""
            a_tag = item.find("a", href=True)
            if a_tag:
                href = a_tag["href"]
                link = href if href.startswith("http") else f"https://propakistani.pk{href}"

            date_tag = item.find("time") or item.find("span", class_=lambda c: c and "date" in str(c).lower())
            date_text = date_tag.get_text(strip=True) if date_tag else ""
            date_val = _parse_date_flexible(date_text) if date_text else None

            if _in_date_window(date_val, curr_dt, lookback_days):
                date_display = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
                articles.append(f"- [{date_display}] {title}")

        if not articles:
            return f"[ProPakistani] No recent news found for {ticker_upper}."

        header = f"## ProPakistani News for {ticker_upper} (last {lookback_days} days from {curr_date}):\n\n"
        return header + "\n".join(articles[:15])
    except Exception as e:
        return f"[ProPakistani] Could not fetch news for {ticker.upper().replace('.KA', '')}: {e}"


def get_psx_news_profit(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """Scrape Profit by Pakistan Today for company news."""
    try:
        ticker_upper = ticker.upper().replace(".KA", "")
        company_name = PSX_COMPANY_NAMES.get(ticker_upper, ticker_upper)
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

        url = f"https://profit.pakistantoday.com.pk/?s={quote_plus(company_name)}"
        resp = _fetch(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []

        for item in soup.find_all(["article", "div"], class_=lambda c: c and ("post" in str(c).lower() or "entry" in str(c).lower())):
            title_tag = item.find(["h2", "h3", "h4"]) or item.find("a")
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title or len(title) < 10:
                continue

            date_tag = item.find("time") or item.find("span", class_=lambda c: c and "date" in str(c).lower())
            date_text = date_tag.get_text(strip=True) if date_tag else ""
            date_val = _parse_date_flexible(date_text) if date_text else None

            if _in_date_window(date_val, curr_dt, lookback_days):
                date_display = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
                articles.append(f"- [{date_display}] {title}")

        if not articles:
            return f"[Profit] No recent news found for {ticker_upper}."

        header = f"## Profit (Pakistan Today) News for {ticker_upper} (last {lookback_days} days from {curr_date}):\n\n"
        return header + "\n".join(articles[:15])
    except Exception as e:
        return f"[Profit] Could not fetch news for {ticker.upper().replace('.KA', '')}: {e}"


def get_psx_news_thenews(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """Scrape The News International (business category) for company news."""
    try:
        ticker_upper = ticker.upper().replace(".KA", "")
        company_name = PSX_COMPANY_NAMES.get(ticker_upper, ticker_upper)
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

        url = f"https://www.thenews.com.pk/search?q={quote_plus(company_name)}&cat=3"
        resp = _fetch(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []

        for item in soup.find_all(["article", "div", "li"], class_=lambda c: c and ("search" in str(c).lower() or "story" in str(c).lower() or "listing" in str(c).lower())):
            title_tag = item.find(["h2", "h3", "h4"]) or item.find("a")
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title or len(title) < 10:
                continue

            date_tag = item.find("time") or item.find("span", class_=lambda c: c and "date" in str(c).lower())
            date_text = date_tag.get_text(strip=True) if date_tag else ""
            date_val = _parse_date_flexible(date_text) if date_text else None

            if _in_date_window(date_val, curr_dt, lookback_days):
                date_display = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
                articles.append(f"- [{date_display}] {title}")

        if not articles:
            return f"[The News] No recent news found for {ticker_upper}."

        header = f"## The News Business for {ticker_upper} (last {lookback_days} days from {curr_date}):\n\n"
        return header + "\n".join(articles[:15])
    except Exception as e:
        return f"[The News] Could not fetch news for {ticker.upper().replace('.KA', '')}: {e}"


def get_sbp_press_releases(curr_date: str, lookback_days: int = 30) -> str:
    """Scrape SBP press releases — monetary policy / rate decisions."""
    try:
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        url = "https://www.sbp.org.pk/press/press.asp"
        resp = _fetch(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        releases = []

        # SBP uses tables with date in one cell, link/title in another
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            # Try to find date and title from cells
            date_val = None
            title = ""
            for cell in cells:
                cell_text = cell.get_text(strip=True)
                parsed = _parse_date_flexible(cell_text)
                if parsed and not date_val:
                    date_val = parsed
                elif not title:
                    a_tag = cell.find("a")
                    if a_tag:
                        a_text = a_tag.get_text(strip=True)
                        if len(a_text) > 10:
                            title = a_text
                    elif len(cell_text) > 10:
                        title = cell_text

            if not title or not date_val:
                continue

            if _in_date_window(date_val, curr_dt, lookback_days):
                date_display = date_val.strftime("%Y-%m-%d")
                releases.append(f"- [{date_display}] {title}")

        # Also check list items / divs as fallback
        if not releases:
            for item in soup.find_all(["li", "div"]):
                links = item.find_all("a", href=True)
                title = ""
                for a in links:
                    a_text = a.get_text(strip=True)
                    if len(a_text) > 10:
                        title = a_text
                        break
                if not title:
                    continue
                text = item.get_text(strip=True)
                date_val = None
                for part in re.split(r"[|\t]", text):
                    parsed = _parse_date_flexible(part.strip())
                    if parsed:
                        date_val = parsed
                        break
                if date_val and _in_date_window(date_val, curr_dt, lookback_days):
                    date_display = date_val.strftime("%Y-%m-%d")
                    releases.append(f"- [{date_display}] {title}")

        if not releases:
            return f"[SBP] No recent press releases found (last {lookback_days} days)."

        header = f"## SBP Press Releases (last {lookback_days} days from {curr_date}):\n\n"
        return header + "\n".join(releases[:10])
    except Exception as e:
        return f"[SBP] Could not fetch press releases: {e}"


# ---------------------------------------------------------------------------
# SCSTrade — now delegated to scstrade.py module (JSON APIs)
# Old HTML scraper replaced by structured API calls.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Nukta Business — YouTube RSS (title-level signal, English titles)
# ---------------------------------------------------------------------------

NUKTA_BUSINESS_CHANNEL_ID = "UCHPjDxfGDT5tnVrsPWmsvjg"  # Nukta Pakistan (main)

def get_nukta_youtube_signals(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """
    Scan Nukta Pakistan YouTube RSS feed for video titles mentioning the company.
    Returns title-level signal (videos in Urdu but titles carry sentiment).
    """
    try:
        bare = ticker.upper().replace(".KA", "")
        company_name = PSX_COMPANY_NAMES.get(bare, bare).lower()
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={NUKTA_BUSINESS_CHANNEL_ID}"
        resp = _fetch(rss_url)
        resp.raise_for_status()

        # Parse XML entries
        entries = re.findall(
            r"<entry>(.*?)</entry>", resp.text, re.DOTALL
        )
        matches = []
        for entry in entries:
            title_m = re.search(r"<title>(.*?)</title>", entry)
            date_m = re.search(r"<published>(.*?)</published>", entry)
            link_m = re.search(r'href="(https://www\.youtube\.com/watch\?v=[^"]+)"', entry)

            if not title_m:
                continue
            title = title_m.group(1).strip()
            date_str = date_m.group(1).strip() if date_m else ""
            link = link_m.group(1) if link_m else ""

            # Check if title mentions the company or ticker
            title_lower = title.lower()
            if bare.lower() not in title_lower and company_name not in title_lower:
                continue

            date_val = _parse_date_flexible(date_str[:10]) if date_str else None
            if not _in_date_window(date_val, curr_dt, lookback_days):
                continue

            date_display = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
            matches.append(f"- [{date_display}] 📺 {title}" + (f"\n  {link}" if link else ""))

        if not matches:
            return f"[Nukta] No recent videos mentioning {bare} found."

        header = f"## Nukta Pakistan — Video Titles mentioning {bare}:\n\n"
        return header + "\n".join(matches[:10])
    except Exception as e:
        return f"[Nukta] Could not fetch YouTube feed: {e}"


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def get_news_psx(ticker: str, start_date: str, end_date: str) -> str:
    """
    Main company news entry point — combines PSX announcements + multiple
    Pakistani news sources. Never raises; always returns a string.

    Signature matches get_news_yfinance(ticker, start_date, end_date).
    """
    try:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            lookback_days = max((end_dt - start_dt).days, 1)
            curr_date = end_date
        except ValueError:
            curr_date = end_date if end_date else start_date
            lookback_days = 7

        scrapers = [
            ("PSX Announcements", lambda: get_psx_announcements(ticker, curr_date, lookback_days)),
            ("Business Recorder", lambda: get_psx_news_brecorder(ticker, curr_date, lookback_days)),
            ("ProPakistani", lambda: get_psx_news_propakistani(ticker, curr_date, lookback_days)),
            ("Profit", lambda: get_psx_news_profit(ticker, curr_date, lookback_days)),
            ("The News", lambda: get_psx_news_thenews(ticker, curr_date, lookback_days)),
            ("SCSTrade Announcements", lambda: get_scstrade_announcements(ticker, curr_date, lookback_days)),
            ("SCSTrade News", lambda: _scstrade_news(ticker, curr_date, lookback_days)),
            ("SCSTrade Research", lambda: get_scstrade_research(ticker)),
            ("Nukta", lambda: get_nukta_youtube_signals(ticker, curr_date, lookback_days)),
        ]

        parts = []
        for name, scrape_fn in scrapers:
            try:
                parts.append(scrape_fn())
            except Exception as e:
                parts.append(f"[{name}] Error: {e}")

        combined = "\n\n".join(parts)
        if not combined.strip():
            return f"No news found for {ticker} between {start_date} and {end_date}."
        return combined
    except Exception as e:
        return f"[PSX News] Unexpected error fetching news for {ticker}: {e}"


def get_global_news_psx(curr_date: str, look_back_days: int = 7, limit: int = 10) -> str:
    """
    Pakistan macro/market news (KSE-100 index, SBP policy, economy).
    Never raises; always returns a string.

    Signature matches get_global_news_yfinance(curr_date, look_back_days, limit).
    """
    try:
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        all_articles = []

        # Source 1: Business Recorder economy
        try:
            resp = _fetch("https://www.brecorder.com/economy")
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for item in soup.find_all(["article", "div"], class_=lambda c: c and ("story" in str(c).lower() or "article" in str(c).lower())):
                title_tag = item.find(["h2", "h3", "h4", "a"])
                title = title_tag.get_text(strip=True) if title_tag else ""
                if not title or len(title) < 10:
                    continue

                link = ""
                a_tag = item.find("a", href=True)
                if a_tag:
                    href = a_tag["href"]
                    link = href if href.startswith("http") else f"https://www.brecorder.com{href}"

                date_tag = item.find("span", class_=lambda c: c and "date" in str(c).lower())
                if not date_tag:
                    date_tag = item.find("time")
                date_text = date_tag.get_text(strip=True) if date_tag else ""
                date_val = _parse_date_flexible(date_text) if date_text else None

                snippet_tag = item.find("p")
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                if _in_date_window(date_val, curr_dt, look_back_days):
                    date_display = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
                    all_articles.append(
                        f"### {title} ({date_display}, Business Recorder)\n"
                        + (f"{snippet}\n" if snippet else "")
                        + (f"Link: {link}\n" if link else "")
                    )

                if len(all_articles) >= limit:
                    break
        except Exception:
            pass

        # Source 2: Dawn Business
        if len(all_articles) < limit:
            try:
                resp = _fetch("https://www.dawn.com/business")
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                for item in soup.find_all("article"):
                    title_tag = item.find(["h2", "h3", "a"])
                    title = title_tag.get_text(strip=True) if title_tag else ""
                    if not title or len(title) < 10:
                        continue

                    link = ""
                    a_tag = item.find("a", href=True)
                    if a_tag:
                        href = a_tag["href"]
                        link = href if href.startswith("http") else f"https://www.dawn.com{href}"

                    date_tag = item.find("span", class_=lambda c: c and "time" in str(c).lower())
                    if not date_tag:
                        date_tag = item.find("time")
                        if not date_tag:
                            date_tag = item.find("span", class_="timestamp")
                    date_text = date_tag.get_text(strip=True) if date_tag else ""
                    date_val = _parse_date_flexible(date_text) if date_text else None

                    snippet_tag = item.find("p")
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                    if _in_date_window(date_val, curr_dt, look_back_days):
                        date_display = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
                        all_articles.append(
                            f"### {title} ({date_display}, Dawn Business)\n"
                            + (f"{snippet}\n" if snippet else "")
                            + (f"Link: {link}\n" if link else "")
                        )

                    if len(all_articles) >= limit:
                        break
            except Exception:
                pass

        # Source 3: SBP press releases
        if len(all_articles) < limit:
            try:
                sbp = get_sbp_press_releases(curr_date, look_back_days)
                if sbp and "[SBP] No recent" not in sbp and "[SBP] Could not" not in sbp:
                    all_articles.append(sbp)
            except Exception:
                pass

        if not all_articles:
            return f"[Pakistan Macro News] No macro news found for {curr_date} (looked back {look_back_days} days)."

        start_date = (curr_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
        header = f"## Pakistan Macro / Market News, from {start_date} to {curr_date}:\n\n"
        return header + "\n".join(all_articles[:limit])
    except Exception as e:
        return f"[Pakistan Macro News] Unexpected error: {e}"
