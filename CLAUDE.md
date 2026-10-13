# SG Healthcare News MCP Server

Python MCP server (FastMCP, streamable-http transport on port 8000, endpoint `/mcp`)
deployed on an AWS EC2 Ubuntu 24.04 instance via `setup.sh` and the systemd unit
`sg-health-news.service`. It fetches Singapore healthcare news from RSS feeds
(`news_fetcher.py`), caches results in SQLite for 1 hour (`cache.py`), and sends
HTML digest emails via Gmail SMTP (`email_sender.py`). Tools are defined in `server.py`.

## Rules

- Never commit secrets: `.env`, Gmail app passwords, AWS keys, `.pem` files, or
  instance IPs. Credentials come from `.env` (see `.env.example`).
- No paid APIs and no accounts needed for news data. Use SQLite, not Redis.
- `setup.sh` must work on a fresh Ubuntu 24.04 instance using the system `python3`.
- Keep dependencies in `requirements.txt` pinned to a major-version range.

## Code review priorities

When reviewing pull requests, focus on, in order:

1. Security: committed credentials, SQL injection in `cache.py`, unescaped headline
   text in email HTML, unvalidated MCP tool inputs, unsafe network exposure.
2. Correctness: unhandled RSS/SMTP failures, cache key or TTL mistakes, FastMCP API misuse.
3. Deployment: changes to `setup.sh`, the systemd unit, or `requirements.txt` that
   would break a fresh EC2 install or a `git pull` + restart.

Skip style nitpicks.
