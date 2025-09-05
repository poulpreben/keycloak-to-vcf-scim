# Docker Compose Deployment Guide

Simple deployment guide for running the SCIM client on an internal management server using Docker Compose.

## Prerequisites

- Docker and Docker Compose installed
- Access to Keycloak and vCenter SCIM endpoints
- Service account credentials

## Quick Start

### 1. Clone the repository
```bash
git clone <repository-url>
cd scim-client
```

### 2. Create environment file
```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
- `KEYCLOAK_CLIENT_SECRET` - From your Keycloak service account
- `SCIM_ENDPOINT_URL` - Your vCenter SCIM endpoint
- `SCIM_BEARER_TOKEN` - Bearer token for SCIM authentication
- `VCENTER_NAME` - (Optional) Filter by specific vCenter

### 3. Build and start
```bash
# Build the image
docker-compose build

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f

# Check health
curl http://localhost:8000/health
```

## Usage

### Check service status
```bash
# Health check with last sync info
curl http://localhost:8000/health | jq

# Scheduler status
curl http://localhost:8000/api/scheduler/status | jq
```

### Manual sync operations
```bash
# Trigger full sync
curl -X POST http://localhost:8000/api/sync/manual

# Sync only users
curl -X POST http://localhost:8000/api/sync/users

# Sync only groups
curl -X POST http://localhost:8000/api/sync/groups

# Preview sync (dry run)
curl http://localhost:8000/api/sync/preview
```

### View sync results
```bash
# Check last sync from health endpoint
curl -s http://localhost:8000/health | jq '.sync'
```

## Configuration

### Environment Variables

Key settings in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `SYNC_INTERVAL_MINUTES` | How often to sync | 60 |
| `SYNC_DELETE_USERS` | Delete users not in Keycloak | false |
| `LOG_LEVEL` | Logging verbosity | INFO |
| `VCENTER_NAME` | Filter by vCenter hostname | (optional) |

### Resource Limits

Edit `docker-compose.yml` to adjust:
```yaml
deploy:
  resources:
    limits:
      cpus: '1'
      memory: 512M
```

## Monitoring

### Logs
```bash
# Follow logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Logs are also saved to ./logs directory
tail -f logs/scim-sync.log
```

### Health Monitoring
The service exposes `/health` endpoint that returns:
- Service status (healthy/degraded)
- Last sync timestamp
- Last sync results
- Any errors

Example monitoring script:
```bash
#!/bin/bash
while true; do
  STATUS=$(curl -s http://localhost:8000/health | jq -r .status)
  LAST_SYNC=$(curl -s http://localhost:8000/health | jq -r .sync.last_sync_time)
  echo "$(date): Status=$STATUS, Last sync=$LAST_SYNC"
  sleep 60
done
```

## Maintenance

### Stop service
```bash
docker-compose down
```

### Update and restart
```bash
git pull
docker-compose build --no-cache
docker-compose up -d
```

### Backup configuration
```bash
cp .env .env.backup.$(date +%Y%m%d)
```

### Clean up
```bash
# Remove containers and networks
docker-compose down

# Also remove volumes
docker-compose down -v

# Remove old logs
rm -rf logs/*
```

## Troubleshooting

### Service won't start
```bash
# Check logs
docker-compose logs

# Validate configuration
docker-compose config

# Test connectivity to Keycloak
curl -I https://auth.example.com

# Test with debug logging
LOG_LEVEL=DEBUG docker-compose up
```

### Sync failures
```bash
# Check detailed logs
docker-compose logs | grep ERROR

# Test preview mode
curl http://localhost:8000/api/sync/preview

# Verify credentials
docker-compose exec scim-client env | grep -E "KEYCLOAK|SCIM"
```

### High memory usage
```bash
# Check current usage
docker stats scim-client

# Restart to clear memory
docker-compose restart
```

## Security Notes

1. **Port Binding**: Service only binds to localhost (127.0.0.1:8000)
2. **User Deletion**: Disabled by default (`SYNC_DELETE_USERS=false`)
3. **Credentials**: Keep `.env` file secure, add to `.gitignore`
4. **Network**: Runs in isolated bridge network

## Running Multiple Instances

To run multiple instances for different vCenters:

```bash
# Create separate directories
mkdir vcenter1 vcenter2

# Copy docker-compose.yml to each
cp docker-compose.yml vcenter1/
cp docker-compose.yml vcenter2/

# Modify container names and ports in each docker-compose.yml
# vcenter1: container_name: scim-client-vc1, ports: 8001:8000
# vcenter2: container_name: scim-client-vc2, ports: 8002:8000

# Run each with different .env files
cd vcenter1 && docker-compose up -d
cd vcenter2 && docker-compose up -d
```

## Support

- Check logs first: `docker-compose logs`
- Health endpoint: `http://localhost:8000/health`
- Debug mode: Set `LOG_LEVEL=DEBUG` in `.env`