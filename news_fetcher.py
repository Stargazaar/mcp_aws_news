"""
news_fetcher.py
Fetches Singapore healthcare news via Google News RSS.
No API key or account required — uses public RSS feeds only.
"""

import datetime
from typing import Optional
from urllib.parse import quote_plus

import feedparser

# Google News RSS base URL.
# hl=en-SG  → English, Singapore edition
# gl=SG     → Geolocation: Singapore
# ceid=SG:en → Country+language edition
GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search"
    "?q={q}&hl=en-SG&gl=SG&ceid=SG:en"
)

# Channel NewsAsia Singapore RSS (no account needed)
CNA_SG_RSS = (
    "https://www.channelnewsasia.com/api/v1/rss-outbound-feed"
    "?_format=xml&category=10416"
)


def _parse_date(entry) -> Optional[datetime.datetime]:
    """Extract published datetime from a feedparser entry, if available."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime.datetime(*entry.published_parsed[:6])
        except (TypeError, ValueError):
            pass
    return None


def _fetch_feed(url: str) -> list:
    """Fetch and parse a single RSS feed URL. Returns feedparser entries."""
    try:
        feed = feedparser.parse(url)
        return feed.entries or []
    except Exception:
        return []


def fetch_headlines(
    q: str = "singapore healthcare",
    weeks_back: int = 2,
    page_size: int = 20,
) -> list[dict]:
    """
    Fetch news headlines from Google News RSS matching `q`,
    filtered to the past `weeks_back` weeks.

    Returns a list of dicts:
        {title, link, published, source}
    sorted newest-first, deduplicated by title.

    Args:
        q:          Search query, e.g. "singapore healthcare" or "MOH hospital"
        weeks_back: Max age of articles to include (up to ~4 weeks via Google News)
        page_size:  Max number of results to return
    """
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(weeks=weeks_back)
    results: list[dict] = []
    seen_titles: set[str] = set()

    # --- Source 1: Google News RSS (primary) ---
    google_url = GOOGLE_NEWS_RSS.format(q=quote_plus(q))
    for entry in _fetch_feed(google_url):
        title = entry.get("title", "").strip()
        if not title or title.lower() in seen_titles:
            continue

        pub = _parse_date(entry)
        if pub and pub < cutoff:
            continue  # older than requested window

        seen_titles.add(title.lower())
        results.append({
            "title": title,
            "link": entry.get("link", ""),
            "published": pub.strftime("%Y-%m-%d") if pub else "unknown",
            "source": entry.get("source", {}).get("title", "Google News"),
        })

    # --- Source 2: CNA Singapore (secondary, health-tagged articles only) ---
    health_keywords = {"health", "hospital", "clinic", "moh", "patient", "medical",
                       "healthcare", "disease", "vaccine", "polyclinic", "mhc"}
    for entry in _fetch_feed(CNA_SG_RSS):
        title = entry.get("title", "").strip()
        if not title or title.lower() in seen_titles:
            continue
        # Only keep CNA entries that mention a health keyword
        if not any(kw in title.lower() for kw in health_keywords):
            continue

        pub = _parse_date(entry)
        if pub and pub < cutoff:
            continue

        seen_titles.add(title.lower())
        results.append({
            "title": title,
            "link": entry.get("link", ""),
            "published": pub.strftime("%Y-%m-%d") if pub else "unknown",
            "source": "Channel NewsAsia",
        })

    # Sort newest-first (unknown dates go last)
    results.sort(key=lambda h: h["published"], reverse=True)
    return results[:page_size]
