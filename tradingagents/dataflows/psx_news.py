"""PSX news scraping — Business Recorder, Dawn Business, and PSX announcements."""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

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

_REQUEST_TIMEOUT = 15
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


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


def get_psx_announcements(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """
    Scrape PSX official announcements for a ticker.
    Source: dps.psx.com.pk/company/{TICKER} announcements section.
    Returns formatted string of announcement titles + dates.
    """
    ticker = ticker.upper().replace(".KA", "")
    url = f"https://dps.psx.com.pk/company/{ticker}"
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        return f"[PSX Announcements] Could not fetch announcements for {ticker}: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")

    announcements = []

    # Look for announcement tables / sections on the page
    # dps.psx.com.pk uses tables with class or specific structure for announcements
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            # Typically: date | description or description | date
            texts = [c.get_text(strip=True) for c in cells]
            # Try to find which cell is the date
            date_val = None
            desc_parts = []
            for text in texts:
                parsed = _parse_date_flexible(text)
                if parsed and not date_val:
                    date_val = parsed
                else:
                    if text:
                        desc_parts.append(text)

            desc = " — ".join(desc_parts) if desc_parts else " | ".join(texts)
            if not desc.strip():
                continue

            if _in_date_window(date_val, curr_dt, lookback_days):
                date_display = date_val.strftime("%Y-%m-%d") if date_val else "N/A"
                announcements.append(f"- [{date_display}] {desc}")

    # Also look for announcement divs / list items
    for div in soup.find_all(["div", "li", "a"], class_=lambda c: c and "announce" in str(c).lower()):
        text = div.get_text(strip=True)
        if text and len(text) > 10:
            announcements.append(f"- {text}")

    if not announcements:
        return f"[PSX Announcements] No announcements found for {ticker} within the last {lookback_days} days."

    header = f"## PSX Announcements for {ticker} (last {lookback_days} days from {curr_date}):\n\n"
    return header + "\n".join(announcements[:50])


def get_psx_news_brecorder(ticker: str, curr_date: str, lookback_days: int = 30) -> str:
    """
    Scrape Business Recorder for company news.
    Returns formatted news items with date, title, snippet.
    """
    ticker_upper = ticker.upper().replace(".KA", "")
    company_name = PSX_COMPANY_NAMES.get(ticker_upper, ticker_upper)
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")

    # Business Recorder search URL
    search_query = company_name.replace(" ", "+")
    url = f"https://www.brecorder.com/search/{search_query}"

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        return f"[Business Recorder] Could not fetch news for {ticker_upper}: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    # BR search results typically have article/story blocks
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

        # Look for date
        date_tag = item.find("span", class_=lambda c: c and "date" in str(c).lower())
        if not date_tag:
            date_tag = item.find("time")
        date_text = date_tag.get_text(strip=True) if date_tag else ""
        date_val = _parse_date_flexible(date_text) if date_text else None

        # Snippet
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

    # Also try story-list / search-result divs
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


def get_news_psx(ticker: str, start_date: str, end_date: str) -> str:
    """
    Main entry point — combines PSX announcements + Business Recorder news.
    Falls back gracefully if scraping fails.

    Signature matches get_news_yfinance(ticker, start_date, end_date).
    """
    # Convert start_date/end_date to curr_date + lookback_days
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        lookback_days = max((end_dt - start_dt).days, 1)
        curr_date = end_date
    except ValueError:
        curr_date = end_date if end_date else start_date
        lookback_days = 7

    parts = []

    # PSX official announcements
    try:
        psx_ann = get_psx_announcements(ticker, curr_date, lookback_days)
        parts.append(psx_ann)
    except Exception as e:
        parts.append(f"[PSX Announcements] Error: {e}")

    # Business Recorder
    try:
        br_news = get_psx_news_brecorder(ticker, curr_date, lookback_days)
        parts.append(br_news)
    except Exception as e:
        parts.append(f"[Business Recorder] Error: {e}")

    combined = "\n\n".join(parts)
    if not combined.strip():
        return f"No news found for {ticker} between {start_date} and {end_date}."

    return combined


def get_global_news_psx(curr_date: str, look_back_days: int = 7, limit: int = 10) -> str:
    """
    Pakistan macro/market news (KSE-100 index, SBP policy, economy).
    Scrapes Business Recorder economy section and Dawn Business.

    Signature matches get_global_news_yfinance(curr_date, look_back_days, limit).
    """
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    all_articles = []

    # Source 1: Business Recorder economy
    try:
        resp = requests.get(
            "https://www.brecorder.com/economy",
            headers=_HEADERS,
            timeout=_REQUEST_TIMEOUT,
        )
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
        pass  # graceful fallback, try next source

    # Source 2: Dawn Business
    if len(all_articles) < limit:
        try:
            resp = requests.get(
                "https://www.dawn.com/business",
                headers=_HEADERS,
                timeout=_REQUEST_TIMEOUT,
            )
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
            pass  # graceful fallback

    if not all_articles:
        return f"[Pakistan Macro News] No macro news found for {curr_date} (looked back {look_back_days} days)."

    start_date = (curr_dt - timedelta(days=look_back_days)).strftime("%Y-%m-%d")
    header = f"## Pakistan Macro / Market News, from {start_date} to {curr_date}:\n\n"
    return header + "\n".join(all_articles[:limit])
