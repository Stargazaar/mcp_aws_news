"""
server.py
SG Healthcare News MCP Server

Exposes four tools via the Model Context Protocol (SSE transport):
  - get_headlines        fetch & cache news from Google News RSS
  - send_digest_email    email top N headlines via Gmail SMTP
  - list_cached_queries  inspect the SQLite cache
  - clear_cache          wipe all cache entries

Transport: HTTP/SSE on port 8000 (configurable via PORT env var)
Claude Desktop connects to: http://<EC2_IP>:8000/sse
"""

import os
from dotenv import load_dotenv

# Load .env file before anything else (local dev + EC2 with .env present)
load_dotenv()

import cache as cache_store
import email_sender
import news_fetcher
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="sg-health-news",
    instructions=(
        "Fetches Singapore healthcare news from Google News RSS and Channel NewsAsia. "
        "Results are cached in SQLite for 1 hour to avoid hammering the feeds. "
        "Can also send an HTML email digest via Gmail. "
        "Default query is 'singapore healthcare'; narrow it with terms like "
        "'MOH Singapore', 'polyclinic', 'hospital restructuring', etc."
    ),
)


# ---------------------------------------------------------------------------
# Tool 1 — get_headlines
# ---------------------------------------------------------------------------

@mcp.tool()
def get_headlines(
    q: str = "singapore healthcare",
    weeks_back: int = 2,
    page_size: int = 10,
) -> str:
    """
    Fetch news headlines matching a query from the past N weeks.
    Results are served from the SQLite cache if a fresh entry exists (< 1 hr old);
    otherwise the RSS feed is fetched live and the result is cached.

    Args:
        q:          Search query, e.g. "singapore healthcare", "MOH hospital",
                    "polyclinic wait time", "dengue outbreak singapore"
        weeks_back: How many weeks back to include. Google News RSS reliably
                    covers ~4 weeks. Older articles may not appear. (default: 2)
        page_size:  Max number of headlines to return, 1–30. (default: 10)
    """
    page_size = max(1, min(30, page_size))
    key = cache_store.make_key(q, weeks_back)

    cached = cache_store.get(key)
    if cached is not None:
        headlines = cached[:page_size]
        data_source = "cache (SQLite)"
    else:
        headlines = news_fetcher.fetch_headlines(q, weeks_back, page_size=30)
        cache_store.set(key, q, headlines)
        data_source = "live (RSS)"

    if not headlines:
        return (
            f"No headlines found for query '{q}' in the past {weeks_back} week(s).\n"
            "Try broadening the query or increasing weeks_back."
        )

    lines = [
        f"Source: {data_source}",
        f"Query:  '{q}'  |  Past {weeks_back} week(s)  |  {len(headlines)} result(s)\n",
    ]
    for i, h in enumerate(headlines, 1):
        lines.append(f"{i}. {h['title']}")
        lines.append(f"   {h['source']}  ·  {h['published']}")
        lines.append(f"   {h['link']}\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 2 — send_digest_email
# ---------------------------------------------------------------------------

@mcp.tool()
def send_digest_email(
    to_email: str,
    q: str = "singapore healthcare",
    weeks_back: int = 2,
    top_n: int = 5,
) -> str:
    """
    Fetch the top N headlines and send them as an HTML email digest via Gmail.
    Headlines are pulled from cache if available; otherwise fetched live.

    Requires these environment variables to be set (see .env.example):
        GMAIL_USER           your Gmail address
        GMAIL_APP_PASSWORD   16-character Google App Password

    Args:
        to_email:   Recipient email address, e.g. "you@example.com"
        q:          Search query (same as get_headlines)
        weeks_back: Time window in weeks (default: 2)
        top_n:      Number of headlines to include in the email, 1–10 (default: 5)
    """
    top_n = max(1, min(10, top_n))
    key = cache_store.make_key(q, weeks_back)

    cached = cache_store.get(key)
    if cached is not None:
        headlines = cached[:top_n]
    else:
        headlines = news_fetcher.fetch_headlines(q, weeks_back, page_size=top_n)
        cache_store.set(key, q, headlines)

    if not headlines:
        return f"No headlines found for '{q}'. Email not sent."

    try:
        email_sender.send_digest(to_email, headlines[:top_n], q, weeks_back)
    except EnvironmentError as e:
        return f"Configuration error: {e}"
    except Exception as e:
        return f"Failed to send email: {e}"

    return (
        f"Email sent to {to_email}.\n"
        f"Included {len(headlines[:top_n])} headlines for '{q}' (past {weeks_back}w)."
    )


# ---------------------------------------------------------------------------
# Tool 3 — list_cached_queries
# ---------------------------------------------------------------------------

@mcp.tool()
def list_cached_queries() -> str:
    """
    Show all queries currently stored in the SQLite cache,
    along with when they were fetched and how old they are.
    Entries expire after 1 hour and are refreshed on the next get_headlines call.
    """
    entries = cache_store.list_entries()
    if not entries:
        return "The cache is empty. Call get_headlines to populate it."

    lines = [f"{len(entries)} cached query/queries:\n"]
    for e in entries:
        age = f"{e['age_minutes']} min ago"
        lines.append(f"  [{e['key']}]  \"{e['query']}\"  —  fetched {e['fetched_at']}  ({age})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 4 — clear_cache
# ---------------------------------------------------------------------------

@mcp.tool()
def clear_cache() -> str:
    """
    Delete all entries from the SQLite cache.
    The next call to get_headlines will fetch fresh data from the RSS feed.
    """
    n = cache_store.clear_all()
    return f"Cleared {n} cache entry/entries. Cache is now empty."


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    # Bind to all interfaces so Claude Desktop can reach us over the public internet.
    # Default is 127.0.0.1 (localhost only) which blocks external connections.
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port

    # DNS rebinding protection defaults to localhost-only allowed hosts.
    # Disable it so Claude Desktop connecting via EC2 public IP is accepted.
    mcp.settings.transport_security.enable_dns_rebinding_protection = False

    print(f"Starting SG Health News MCP server on port {port} ...")
    print(f"Claude Desktop SSE URL: http://<EC2_PUBLIC_IP>:{port}/sse")
    mcp.run(transport="sse")
