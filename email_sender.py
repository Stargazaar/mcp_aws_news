"""
email_sender.py
Sends an HTML news digest email via Gmail SMTP.
Uses Python's built-in smtplib — no extra packages needed.

Setup (one-time):
  1. Go to myaccount.google.com → Security → 2-Step Verification → App passwords
  2. Create an App Password for "Mail" on "Other device"
  3. Put the 16-char password in your .env file as GMAIL_APP_PASSWORD
"""

import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(
            f"Environment variable '{name}' is not set. "
            "Check your .env file and ensure python-dotenv loaded it."
        )
    return value


def _build_html(headlines: list[dict], q: str, weeks_back: int) -> str:
    """Render a clean HTML email body."""
    rows = ""
    for i, h in enumerate(headlines, 1):
        rows += f"""
        <tr>
          <td style="padding:10px 6px;font-size:13px;color:#888;vertical-align:top;">{i}</td>
          <td style="padding:10px 6px;">
            <a href="{h['link']}" style="color:#1a73e8;text-decoration:none;font-size:15px;font-weight:500;">
              {h['title']}
            </a>
            <br>
            <span style="color:#999;font-size:12px;">{h['source']} &middot; {h['published']}</span>
          </td>
        </tr>"""

    generated = datetime.now().strftime("%d %b %Y, %H:%M")
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:24px;color:#333;">
  <h2 style="margin-bottom:4px;">SG Healthcare News Digest</h2>
  <p style="color:#666;font-size:13px;margin-top:0;">
    Query: <b>{q}</b> &nbsp;|&nbsp; Past <b>{weeks_back}</b> week(s) &nbsp;|&nbsp; Generated {generated}
  </p>
  <table style="border-collapse:collapse;width:100%;margin-top:16px;">
    <thead>
      <tr style="background:#f8f9fa;border-bottom:2px solid #dee2e6;">
        <th style="padding:10px 6px;text-align:left;font-size:13px;color:#555;width:30px;">#</th>
        <th style="padding:10px 6px;text-align:left;font-size:13px;color:#555;">Headline</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="color:#bbb;font-size:11px;margin-top:32px;border-top:1px solid #eee;padding-top:12px;">
    Sent by <code>sg-health-news-mcp</code> running on AWS EC2 &nbsp;&middot;&nbsp;
    <a href="https://github.com" style="color:#bbb;">View on GitHub</a>
  </p>
</body>
</html>"""


def _build_plain(headlines: list[dict], q: str, weeks_back: int) -> str:
    """Plain-text fallback for email clients that don't render HTML."""
    lines = [
        f"SG Healthcare News Digest",
        f"Query: {q} | Past {weeks_back} week(s)",
        f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}",
        "",
    ]
    for i, h in enumerate(headlines, 1):
        lines.append(f"{i}. {h['title']}")
        lines.append(f"   {h['source']} · {h['published']}")
        lines.append(f"   {h['link']}")
        lines.append("")
    return "\n".join(lines)


def send_digest(
    to_email: str,
    headlines: list[dict],
    q: str,
    weeks_back: int,
) -> None:
    """
    Send the top headlines as an HTML email via Gmail SMTP.

    Reads credentials from environment variables:
        GMAIL_USER          your.email@gmail.com
        GMAIL_APP_PASSWORD  16-character App Password (spaces optional)

    Raises:
        EnvironmentError  if credentials are missing
        smtplib.SMTPException  on send failure
    """
    gmail_user = _require_env("GMAIL_USER")
    app_password = _require_env("GMAIL_APP_PASSWORD").replace(" ", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[SG Health] {q} — top {len(headlines)} headlines (past {weeks_back}w)"
    msg["From"] = f"SG Health News <{gmail_user}>"
    msg["To"] = to_email

    msg.attach(MIMEText(_build_plain(headlines, q, weeks_back), "plain"))
    msg.attach(MIMEText(_build_html(headlines, q, weeks_back), "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(gmail_user, app_password)
        smtp.sendmail(gmail_user, to_email, msg.as_string())
