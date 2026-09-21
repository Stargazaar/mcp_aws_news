#!/usr/bin/env bash
# setup.sh
# One-shot bootstrap script for Ubuntu 22.04 EC2 instance.
# Run once after SSH-ing into the instance:
#   chmod +x setup.sh && ./setup.sh
set -euo pipefail

PROJECT_DIR="$HOME/mcp_aws_news"
SERVICE_NAME="sg-health-news"

echo "==> [1/6] Updating system packages..."
sudo apt-get update -y -q
sudo apt-get install -y -q python3.11 python3.11-venv python3-pip git

echo "==> [2/6] Cloning / updating project..."
if [ -d "$PROJECT_DIR/.git" ]; then
    cd "$PROJECT_DIR" && git pull
else
    # Replace the URL below with your actual GitHub repo URL after pushing
    git clone https://github.com/YOUR_USERNAME/mcp_aws_news.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

echo "==> [3/6] Creating Python virtual environment..."
python3.11 -m venv "$PROJECT_DIR/venv"
source "$PROJECT_DIR/venv/bin/activate"

echo "==> [4/6] Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r "$PROJECT_DIR/requirements.txt" -q

echo "==> [5/6] Setting up .env file..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo ""
    echo "  ACTION REQUIRED: Edit your credentials file:"
    echo "    nano $PROJECT_DIR/.env"
    echo "  Fill in GMAIL_USER and GMAIL_APP_PASSWORD, then re-run: sudo systemctl restart $SERVICE_NAME"
    echo ""
fi

echo "==> [6/6] Installing and enabling systemd service..."
sudo cp "$PROJECT_DIR/sg-health-news.service" /etc/systemd/system/
# Patch the service file with the actual home directory path
sudo sed -i "s|/home/ubuntu|$HOME|g" /etc/systemd/system/sg-health-news.service
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo ""
echo "======================================================"
echo " Setup complete!"
echo " Service status:  sudo systemctl status $SERVICE_NAME"
echo " Live logs:       sudo journalctl -u $SERVICE_NAME -f"
echo " MCP SSE URL:     http://$(curl -s ifconfig.me):8000/sse"
echo "======================================================"
