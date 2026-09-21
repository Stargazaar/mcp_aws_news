# SG Healthcare News MCP Server on AWS EC2

A learning project that deploys a Python [MCP](https://modelcontextprotocol.io/) server onto an AWS EC2 free-tier instance. Claude Desktop connects to the server and can fetch Singapore healthcare news headlines and send email digests — all via natural language.

## What you will learn

| Concept | Where you see it |
|---|---|
| AWS EC2 fundamentals | Launch, key pairs, security groups, SSH |
| Linux service management | systemd unit file, journalctl logs |
| Model Context Protocol (MCP) | FastMCP, SSE transport, tool definitions |
| RSS feed parsing | `feedparser`, Google News RSS |
| SQLite caching | TTL cache, cache invalidation |
| Gmail SMTP | App Passwords, `smtplib`, HTML email |
| Python project structure | Modules, `.env`, `requirements.txt` |

## Architecture

```
Your Windows PC
  Claude Desktop ──────── HTTP/SSE (port 8000) ──────► EC2 t2.micro
                                                         Ubuntu 22.04
                                                         Python 3.11
                                                         FastMCP server
                                                           ├── get_headlines()
                                                           ├── send_digest_email()
                                                           ├── list_cached_queries()
                                                           └── clear_cache()
                                                         SQLite cache.db
                                                              │
                                                         Google News RSS
                                                         Channel NewsAsia RSS
                                                              │
                                                         Gmail SMTP ──► your inbox
```

## Project structure

```
mcp_aws_news/
├── server.py               # FastMCP entry point — 4 MCP tools
├── news_fetcher.py         # Google News + CNA RSS parser
├── cache.py                # SQLite TTL cache
├── email_sender.py         # Gmail SMTP HTML digest
├── requirements.txt        # pip dependencies
├── .env.example            # credential template (copy to .env)
├── .gitignore              # excludes .env, cache.db, venv/
├── setup.sh                # one-shot EC2 bootstrap script
├── sg-health-news.service  # systemd unit file
└── README.md               # this file
```

---

## Part 1 — GitHub setup (do this first)

1. Create a new **public or private** repo on [github.com](https://github.com) named `mcp_aws_news`
2. Push this project:
   ```powershell
   cd "C:\Users\limqi\Desktop\Python\Projects\mcp_aws_news"
   git remote add origin https://github.com/Stargazaar/mcp_aws_news.git
   git push -u origin main
   ```
3. In `setup.sh`, replace `YOUR_USERNAME` with your GitHub username

---

## Part 2 — Launch EC2 instance

### 2.1 Open the EC2 console

1. Log in to [console.aws.amazon.com](https://console.aws.amazon.com)
2. Top-right region selector → choose **Asia Pacific (Singapore) `ap-southeast-1`**
   *(closest to you, makes sense for an SG news project)*
3. Search bar → **EC2** → click **Launch instance**

### 2.2 Configure the instance

| Setting | Value |
|---|---|
| Name | `sg-health-news-mcp` |
| AMI | **Ubuntu Server 22.04 LTS** (Free tier eligible) |
| Architecture | 64-bit (x86) |
| Instance type | **t2.micro** (Free tier: 750 hrs/month for 12 months) |
| Key pair | Create new → see 2.3 below |
| Storage | 8 GiB gp3 (free tier includes 30 GiB) |

### 2.3 Create a key pair

1. Click **Create new key pair**
2. Name: `sg-health-news-key`
3. Key pair type: **RSA**
4. Private key file format: **.pem** (works with Windows OpenSSH)
5. Click **Create key pair** — a `.pem` file downloads automatically
6. Save it somewhere permanent, e.g. `C:\Users\limqi\.ssh\sg-health-news-key.pem`

### 2.4 Configure security group

Click **Edit** next to Network settings, then add these inbound rules:

| Type | Port | Source | Purpose |
|---|---|---|---|
| SSH | 22 | 0.0.0.0/0 | SSH from any network (key file is the protection) |
| Custom TCP | 8000 | 0.0.0.0/0 | MCP server (Claude Desktop connects here) |

> **Security note**: Both ports are open to the internet. SSH is protected by your `.pem`
> key file — anyone without it cannot connect. Port 8000 has no authentication, which is
> fine for a learning project. Do not store secrets or sensitive data on this instance.

### 2.5 Launch

Click **Launch instance**. Wait ~60 seconds. Note down the **Public IPv4 address** from the instance details page — you will need it in every step below.

---

## Part 3 — SSH into EC2 from Windows

### 3.1 Fix key file permissions (required on Windows)

Open **PowerShell** (not Command Prompt):

```powershell
$key = "C:\Users\limqi\.ssh\sg-health-news-key.pem"
icacls $key /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

Without this step, SSH refuses the key with a "bad permissions" error.

### 3.2 Connect

```powershell
ssh -i "C:\Users\limqi\.ssh\sg-health-news-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```

Replace `YOUR_EC2_PUBLIC_IP` with the actual IP from step 2.5.
Type `yes` when asked to confirm the fingerprint. You are now inside the EC2 instance.

---

## Part 4 — Deploy the server

### 4.1 Run the setup script

Inside the EC2 SSH session:

```bash
git clone https://github.com/YOUR_USERNAME/mcp_aws_news.git ~/mcp_aws_news
cd ~/mcp_aws_news
chmod +x setup.sh
./setup.sh
```

The script:
- Installs Python 3.11 and git
- Creates a Python virtual environment in `~/mcp_aws_news/venv/`
- Installs `requirements.txt`
- Installs and enables the systemd service

### 4.2 Configure Gmail credentials

```bash
nano ~/mcp_aws_news/.env
```

Fill in:
```
GMAIL_USER=your.email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

**How to get a Gmail App Password:**
1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already on
3. Go back to Security → scroll down to **App passwords**
4. App: **Mail** | Device: **Other** → name it `ec2-mcp` → click **Generate**
5. Copy the 16-character password into `.env`

Save with `Ctrl+O`, exit with `Ctrl+X`.

### 4.3 Restart the service

```bash
sudo systemctl restart sg-health-news
sudo systemctl status sg-health-news   # should show "active (running)"
```

### 4.4 Verify the server is up

```bash
curl http://localhost:8000/sse
```

You should see an SSE stream starting with `event: endpoint`. Press `Ctrl+C` to stop.

### 4.5 Useful commands

```bash
# Live logs
sudo journalctl -u sg-health-news -f

# Restart after code changes
sudo systemctl restart sg-health-news

# Stop the service
sudo systemctl stop sg-health-news

# Check what port it is listening on
ss -tlnp | grep 8000
```

---

## Part 5 — Install and configure Claude Desktop

### 5.1 Install Claude Desktop

Download from [claude.ai/download](https://claude.ai/download) and install.

### 5.2 Edit the MCP config file

Open this file in Notepad (create it if it does not exist):
```
C:\Users\limqi\AppData\Roaming\Claude\claude_desktop_config.json
```

Paste:
```json
{
  "mcpServers": {
    "sg-health-news": {
      "url": "http://YOUR_EC2_PUBLIC_IP:8000/sse"
    }
  }
}
```

Replace `YOUR_EC2_PUBLIC_IP` with your instance's public IP.

### 5.3 Restart Claude Desktop

Fully quit and reopen Claude Desktop. In the bottom-left of the chat input you should see a small tools icon — clicking it shows your connected MCP server.

---

## Part 6 — Test it

Try these prompts in Claude Desktop:

```
Get me the latest Singapore healthcare news from the past 2 weeks.
```

```
Search for news about polyclinics or MOH announcements in the past month.
```

```
Send me a digest of the top 5 Singapore healthcare headlines to my.email@gmail.com
```

```
Show me what's in the news cache, then clear it and fetch fresh results.
```

---

## Part 7 — Cost control (important)

The t2.micro is free for **750 hours/month** on new accounts (12 months).
That is enough to run it 24/7, but here is how to stop it when not using it:

**Stop the instance** (data is preserved, no hourly charge):
1. EC2 Console → Instances → select your instance → Instance state → **Stop**

**Start it again**:
- Instance state → **Start**
- **Note**: the Public IP changes every time you start/stop. Update `claude_desktop_config.json` with the new IP.

To get a fixed IP (optional, ~$3.60/month when running, free when attached to a running instance):
- Elastic IP → Allocate → Associate with your instance

---

## What MCP is (plain English)

Without MCP, Claude only knows what it was trained on — no live data, no external tools.

With MCP, Claude can call functions on your server **during a conversation**:

```
User:    "What are the latest SG healthcare headlines?"

Claude:  [calls get_headlines("singapore healthcare", weeks_back=2)]
         [receives structured list back from your EC2 server]
         [summarises and responds]

Claude:  "Here are the top headlines from the past 2 weeks: ..."
```

MCP standardises this with a JSON protocol over HTTP/SSE, so any MCP-compatible client
(Claude Desktop, Cursor, custom apps) can talk to any MCP server you write.

---

## Key concepts recap

| Concept | File | What to read |
|---|---|---|
| MCP tool definition | `server.py` | `@mcp.tool()` decorator, docstrings as tool descriptions |
| SSE transport | `server.py` | `mcp.run(transport="sse", ...)` |
| RSS parsing | `news_fetcher.py` | `feedparser.parse(url)`, date filtering |
| SQLite cache | `cache.py` | `make_key()`, TTL check, `INSERT OR REPLACE` |
| Gmail SMTP | `email_sender.py` | `smtplib.SMTP`, `starttls()`, `MIMEMultipart` |
| systemd service | `sg-health-news.service` | `EnvironmentFile`, `Restart=always` |
