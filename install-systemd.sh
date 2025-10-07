#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}SCIM Client Systemd Service Installation${NC}"
echo "========================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}" 
   exit 1
fi

# Configuration
SERVICE_NAME="scim-client"
SERVICE_USER="scim-client"
SERVICE_GROUP="scim-client"
INSTALL_DIR="/opt/scim-client"
ENV_DIR="/etc/scim-client"

echo -e "${YELLOW}Step 1: Creating service user...${NC}"
if id "$SERVICE_USER" &>/dev/null; then
    echo "User $SERVICE_USER already exists"
else
    useradd --system --shell /bin/false --home-dir /nonexistent --no-create-home "$SERVICE_USER"
    echo "Created system user: $SERVICE_USER"
fi

echo -e "${YELLOW}Step 2: Creating directories...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$ENV_DIR"
chmod 750 "$ENV_DIR"

echo -e "${YELLOW}Step 3: Installing uv if not present...${NC}"
if command -v uv &> /dev/null; then
    echo "uv is already installed"
    UV_BIN=$(which uv)
elif [ -f "/usr/local/bin/uv" ]; then
    echo "uv found at /usr/local/bin/uv"
    UV_BIN="/usr/local/bin/uv"
else
    echo "Installing uv to /usr/local/bin..."
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh
    # Check if installation succeeded
    if [ -f "/usr/local/bin/uv" ]; then
        UV_BIN="/usr/local/bin/uv"
        echo "uv installed successfully at $UV_BIN"
    else
        echo -e "${RED}Failed to install uv${NC}"
        exit 1
    fi
fi

echo -e "${YELLOW}Step 4: Copying project files...${NC}"
# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Copy project files
cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/pyproject.toml" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/uv.lock" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/main.py" "$INSTALL_DIR/" 2>/dev/null || true  # Optional if exists

echo -e "${YELLOW}Step 5: Setting up environment files...${NC}"
# Copy environment files if they exist
if [ -f "$SCRIPT_DIR/.env.PROD" ]; then
    cp "$SCRIPT_DIR/.env.PROD" "$ENV_DIR/.env.PROD"
    chmod 640 "$ENV_DIR/.env.PROD"
    chown root:$SERVICE_GROUP "$ENV_DIR/.env.PROD"
    echo "Copied .env.PROD to $ENV_DIR/"
else
    echo -e "${YELLOW}Warning: .env.PROD not found. Please create it at $ENV_DIR/.env.PROD${NC}"
fi

# Create symlink for environment file
ln -sf "$ENV_DIR/.env.PROD" "$INSTALL_DIR/.env.PROD"

echo -e "${YELLOW}Step 6: Setting permissions...${NC}"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

echo -e "${YELLOW}Step 7: Installing systemd service...${NC}"
cp "$SCRIPT_DIR/scim-client.service" /etc/systemd/system/
systemctl daemon-reload

echo -e "${YELLOW}Step 8: Enabling service...${NC}"
systemctl enable scim-client.service

echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Configure your environment in: $ENV_DIR/.env.PROD"
echo "2. Start the service: systemctl start scim-client"
echo "3. Check status: systemctl status scim-client"
echo "4. View logs: journalctl -u scim-client -f"
echo ""
echo "Service management commands:"
echo "  Start:   systemctl start scim-client"
echo "  Stop:    systemctl stop scim-client"
echo "  Restart: systemctl restart scim-client"
echo "  Status:  systemctl status scim-client"
echo "  Logs:    journalctl -u scim-client -f"