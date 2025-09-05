# Systemd Service Deployment Guide

Deployment guide for running the SCIM client as a systemd service using `uv` directly.

## Prerequisites

- Linux system with systemd
- Python 3.13+
- `uv` package manager
- sudo/root access for installation

## Quick Installation

### Automated Installation

```bash
# Clone the repository
git clone <repository-url>
cd scim-client

# Configure environment
cp .env.example .env
nano .env  # Add your credentials

# Run installer (as root)
sudo ./install-systemd.sh

# Start service
sudo systemctl start scim-client

# Check status
sudo systemctl status scim-client
```

## Manual Installation

### 1. Install uv (if not installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Create service user
```bash
sudo useradd --system --no-create-home --shell /bin/false scimclient
```

### 3. Set up application directory
```bash
# Create directory
sudo mkdir -p /opt/scim-client
sudo mkdir -p /opt/scim-client/logs

# Copy files
sudo cp -r src pyproject.toml uv.lock /opt/scim-client/
cd /opt/scim-client

# Install dependencies
sudo uv sync --frozen

# Set permissions
sudo chown -R scimclient:scimclient /opt/scim-client
```

### 4. Configure environment
```bash
# Copy and edit configuration
sudo cp .env.example /opt/scim-client/.env
sudo nano /opt/scim-client/.env

# Set secure permissions
sudo chmod 640 /opt/scim-client/.env
sudo chown scimclient:scimclient /opt/scim-client/.env
```

### 5. Install systemd service
```bash
# Copy service file
sudo cp scim-client.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable scim-client
sudo systemctl start scim-client
```

## Service Management

### Basic Commands
```bash
# Start service
sudo systemctl start scim-client

# Stop service
sudo systemctl stop scim-client

# Restart service
sudo systemctl restart scim-client

# Check status
sudo systemctl status scim-client

# Enable auto-start on boot
sudo systemctl enable scim-client

# Disable auto-start
sudo systemctl disable scim-client
```

### View Logs
```bash
# Follow logs in real-time
sudo journalctl -u scim-client -f

# View last 100 lines
sudo journalctl -u scim-client -n 100

# View logs from today
sudo journalctl -u scim-client --since today

# View logs with timestamps
sudo journalctl -u scim-client --output=short-iso
```

### Health Monitoring
```bash
# Check service health
curl http://localhost:8000/health | jq

# Check scheduler status
curl http://localhost:8000/api/scheduler/status | jq

# Monitor service
watch -n 30 'systemctl status scim-client'
```

## Configuration

### Environment Variables
Edit `/opt/scim-client/.env`:

```bash
sudo nano /opt/scim-client/.env

# After editing, restart service
sudo systemctl restart scim-client
```

### Service Configuration
Edit `/etc/systemd/system/scim-client.service`:

```bash
sudo nano /etc/systemd/system/scim-client.service

# Reload and restart after changes
sudo systemctl daemon-reload
sudo systemctl restart scim-client
```

Key settings in service file:
- `MemoryLimit=512M` - Adjust memory limit
- `CPUQuota=100%` - Adjust CPU usage
- `RestartSec=10` - Delay between restarts
- `User=scimclient` - Service user

## API Usage

### Manual Sync
```bash
# Trigger full sync
curl -X POST http://localhost:8000/api/sync/manual

# Sync users only
curl -X POST http://localhost:8000/api/sync/users

# Sync groups only
curl -X POST http://localhost:8000/api/sync/groups
```

### Monitoring Script
Create `/usr/local/bin/scim-client-monitor`:

```bash
#!/bin/bash
# SCIM Client Monitor

check_health() {
    STATUS=$(curl -s http://localhost:8000/health | jq -r .status)
    LAST_SYNC=$(curl -s http://localhost:8000/health | jq -r .sync.last_sync_time)
    echo "Status: $STATUS"
    echo "Last Sync: $LAST_SYNC"
}

check_service() {
    if systemctl is-active --quiet scim-client; then
        echo "Service: Running"
    else
        echo "Service: Stopped"
    fi
}

echo "=== SCIM Client Status ==="
check_service
check_health
```

Make it executable:
```bash
sudo chmod +x /usr/local/bin/scim-client-monitor
```

## Updates

### Update Application
```bash
# Stop service
sudo systemctl stop scim-client

# Backup current installation
sudo cp -r /opt/scim-client /opt/scim-client.backup

# Update code
cd /path/to/repo
git pull

# Copy updated files
sudo cp -r src pyproject.toml uv.lock /opt/scim-client/

# Update dependencies
cd /opt/scim-client
sudo uv sync --frozen

# Fix permissions
sudo chown -R scimclient:scimclient /opt/scim-client

# Start service
sudo systemctl start scim-client
```

### Rollback
```bash
# Stop service
sudo systemctl stop scim-client

# Restore backup
sudo rm -rf /opt/scim-client
sudo mv /opt/scim-client.backup /opt/scim-client

# Start service
sudo systemctl start scim-client
```

## Troubleshooting

### Service Won't Start
```bash
# Check service status
sudo systemctl status scim-client

# Check journal for errors
sudo journalctl -u scim-client --since "5 minutes ago"

# Test configuration
cd /opt/scim-client
sudo -u scimclient /usr/local/bin/uv run python -m src.main
```

### Permission Issues
```bash
# Fix ownership
sudo chown -R scimclient:scimclient /opt/scim-client

# Fix .env permissions
sudo chmod 640 /opt/scim-client/.env

# Fix log directory
sudo chmod 755 /opt/scim-client/logs
```

### High Memory Usage
```bash
# Check current usage
systemctl show scim-client | grep -i memory

# Edit memory limit
sudo nano /etc/systemd/system/scim-client.service
# Change: MemoryLimit=256M

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart scim-client
```

### Debug Mode
```bash
# Enable debug logging
sudo nano /opt/scim-client/.env
# Set: LOG_LEVEL=DEBUG

# Restart and watch logs
sudo systemctl restart scim-client
sudo journalctl -u scim-client -f
```

## Security

### File Permissions
```bash
/opt/scim-client/        # 750 (rwxr-x---)
/opt/scim-client/.env    # 640 (rw-r-----)
/opt/scim-client/logs/   # 755 (rwxr-xr-x)
```

### Network Security
The service binds to localhost only (127.0.0.1:8000). For external access, use a reverse proxy:

```nginx
# nginx example
location /scim-client/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

### Systemd Security
The service includes security hardening:
- `NoNewPrivileges=true` - Prevent privilege escalation
- `PrivateTmp=true` - Isolated /tmp
- `ProtectSystem=strict` - Read-only filesystem
- `ProtectHome=true` - No access to /home

## Uninstall

```bash
# Stop and disable service
sudo systemctl stop scim-client
sudo systemctl disable scim-client

# Remove service file
sudo rm /etc/systemd/system/scim-client.service

# Remove application
sudo rm -rf /opt/scim-client

# Remove user (optional)
sudo userdel scimclient

# Reload systemd
sudo systemctl daemon-reload
```