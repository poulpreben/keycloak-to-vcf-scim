# SCIM Client for VMware Cloud Foundation

Automates user provisioning from Keycloak to VMware Cloud Foundation via SCIM 2.0 protocol.

## Overview

This application synchronizes users and groups from Keycloak to VMware Cloud Foundation using the SCIM 2.0 standard, similar to how Okta or other identity providers integrate with VMware Cloud Foundation.

**Key Feature**: The sync is filtered by vCenter name - only groups with a matching `vcenter_name` attribute and their members are synchronized. This allows multiple vCenter instances to be managed from a single Keycloak realm.

## Features

- OAuth 2.0 Client Credentials flow authentication with Keycloak
- SCIM 2.0 protocol support for VMware Cloud Foundation
- **Filtered synchronization**: Only syncs groups with matching `vcenter_name` attribute
- **Subgroup support**: Automatically includes subgroups (e.g., serverusers, serveradmins)
- **User deduplication**: Each user synced only once even if in multiple groups
- Automatic periodic synchronization
- Manual sync API endpoints
- Debug endpoints for development
- Docker support
- Multi-environment configuration support

## Architecture

```
Keycloak (IdP) --> SCIM Client --> VMware Cloud Foundation (SCIM 2.0 Endpoint)
```

## Requirements

- Python 3.13+
- Keycloak server with configured client
- VMware Cloud Foundation with SCIM 2.0 endpoint configured
- `uv` package manager

## Setup

### 1. VMware Cloud Foundation Configuration

Follow the VMware documentation to:
1. Set up external identity federation
2. Configure SCIM 2.0 application
3. Generate a bearer token for SCIM authentication
4. Note the SCIM endpoint URL (e.g., `https://vcf.example.com/api/scim/v2`)

Reference: [Create a SCIM 2.0 Application for VMware Cloud Foundation](https://techdocs.broadcom.com/us/en/vmware-cis/vcf/vcf-5-2-and-earlier/5-2/create-a-scim-2-0-application-for-vmware-cloud-foundation.html)

### 2. Keycloak Group Configuration

#### Set up Groups with vCenter Attribute:

1. **Create or modify groups in Keycloak**:
   - Navigate to `Groups` in your realm
   - Create a parent group (e.g., `vcenter01`)
   - Add the `vcenter_name` attribute:
     - Select the group → `Attributes` tab
     - Add attribute: Key = `vcenter_name`, Value = `vcenter01.contoso.com`
   - Create subgroups under this parent (e.g., `serverusers`, `serveradmins`)
   - Add users to these subgroups

2. **Group Structure Example**:
   ```
   vcenter01/                   # Parent group with vcenter_name attribute
   ├── serverusers/             # Subgroup for regular users
   └── serveradmins/            # Subgroup for administrators
   ```

### 3. Keycloak Service Account Configuration

#### Create a Service Account Client in Keycloak:

1. **Login to Keycloak Admin Console**
   - Navigate to `https://your-keycloak.com/admin`
   - Select your realm (or use `master` realm)

2. **Create a New Client**
   - Go to `Clients` � Click `Create client`
   - Fill in the details:
     - **Client type**: `OpenID Connect`
     - **Client ID**: `scim-client` (or your preferred name)
   - Click `Next`

3. **Configure Client Capability**
   - **Client authentication**: `On` (this makes it a confidential client)
   - **Authorization**: `Off` (unless you need fine-grained authorization)
   - **Authentication flow**: Uncheck all except:
     -  Service accounts roles
     -  Direct access grants (optional, for testing)
   - Click `Next`

4. **Configure Login Settings**
   - **Root URL**: Leave blank
   - **Valid redirect URIs**: Leave blank (not needed for service accounts)
   - **Valid post logout redirect URIs**: Leave blank
   - **Web origins**: Leave blank
   - Click `Save`

5. **Copy Client Credentials**
   - Go to the `Credentials` tab
   - Copy the **Client secret** (you'll need this for the `.env` file)

6. **Assign Service Account Roles**
   - Go to the `Service account roles` tab
   - Click `Assign role`
   - Filter by `realm-management` client roles
   - Assign the following roles:
     - `view-users` - Required to read users
     - `view-realm` - Required to read realm configuration
     - `query-users` - Required to search users
     - `query-groups` - Required to search groups
     - `view-clients` - Optional, if you need client information
   - Click `Assign`

   **Alternative for full admin access (not recommended for production):**
   - Assign `realm-admin` role for complete access

7. **Verify Service Account Permissions** (Optional)
   - Go to `Clients` � Select your client � `Service account roles`
   - Click on `Effective roles` to see all inherited permissions
   - Ensure the necessary realm-management roles are listed

8. **Test the Service Account** (Optional)
   ```bash
   # Get access token
   curl -X POST "https://your-keycloak.com/realms/YOUR_REALM/protocol/openid-connect/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "client_id=scim-client" \
     -d "client_secret=YOUR_CLIENT_SECRET" \
     -d "grant_type=client_credentials"
   
   # Test API access (replace ACCESS_TOKEN with the token from above)
   curl -H "Authorization: Bearer ACCESS_TOKEN" \
     "https://your-keycloak.com/admin/realms/YOUR_REALM/users?max=1"
   ```

### 3. Environment Configuration

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Configure the environment variables:
```bash
# Keycloak settings
KEYCLOAK_URL=https://keycloak.example.com
KEYCLOAK_REALM=master
KEYCLOAK_CLIENT_ID=scim-client
KEYCLOAK_CLIENT_SECRET=your-client-secret-from-step-5

# SCIM Endpoint settings
SCIM_ENDPOINT_URL=https://vcf.example.com/api/scim/v2
SCIM_BEARER_TOKEN=your-bearer-token
SCIM_VERIFY_SSL=true

# vCenter filtering settings (optional)
# Only sync groups with matching vcenter_name attribute
VCENTER_NAME=vcenter01.contoso.com  # Auto-extracted from SCIM URL if not set
VCENTER_NAME_ATTRIBUTE=vcenter_name  # Attribute name in Keycloak groups

# Sync settings
SYNC_INTERVAL_MINUTES=60
SYNC_ENABLED=true
```

## Installation

Using uv package manager:
```bash
uv sync
```

## Running

### Development Mode
```bash
uv run python -m src.main
```

### Production with Docker
```bash
docker-compose up --build -d
```

## API Endpoints

### Core Endpoints
- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /api/sync/manual` - Trigger manual full sync
- `POST /api/sync/users` - Sync only users
- `POST /api/sync/groups` - Sync only groups
- `GET /api/scheduler/status` - Get scheduler status
- `POST /api/scheduler/start` - Start scheduler
- `POST /api/scheduler/stop` - Stop scheduler

### Debug Endpoints (DEV mode only)
- `GET /api/debug/sync/preview` - Preview sync without making changes
- `GET /api/debug/keycloak/users` - List Keycloak users
- `GET /api/debug/keycloak/groups` - List Keycloak groups
- `GET /api/debug/scim/test-connection` - Test SCIM endpoint connection
- `GET /api/debug/scim/users` - List users from SCIM endpoint
- `GET /api/debug/config` - View configuration (sensitive data redacted)

## Docker Deployment

### Build and run with Docker:
```bash
docker build -t scim-client .
docker run -p 8000:8000 --env-file .env scim-client
```

### Using docker-compose:
```bash
docker-compose up -d
```

### View logs:
```bash
docker-compose logs -f scim-client
```

## SCIM 2.0 Implementation

This client implements the following SCIM 2.0 operations:
- `POST /Users` - Create user
- `GET /Users` - List/search users
- `PUT /Users/{id}` - Update user
- `DELETE /Users/{id}` - Delete user
- `POST /Groups` - Create group
- `DELETE /Groups/{id}` - Delete group

The implementation follows the SCIM 2.0 RFC specifications and is compatible with VMware Cloud Foundation's SCIM endpoint.

## Security Considerations

- Store sensitive credentials in environment variables
- Use HTTPS for all connections
- Enable SSL verification in production (`SCIM_VERIFY_SSL=true`)
- Run container as non-root user
- Regularly rotate bearer tokens and client secrets
- Use minimal required permissions for Keycloak service account

## Troubleshooting

### Keycloak Issues
- **401 Unauthorized**: Check client credentials and service account is enabled
- **403 Forbidden**: Verify service account has required realm-management roles
- **Empty user list**: Ensure service account has `view-users` and `query-users` permissions

### Connection Issues
- Verify SCIM endpoint URL is correct
- Check bearer token is valid and not expired
- Ensure network connectivity between client and endpoints

### Sync Issues
- Check Keycloak client has proper permissions
- Verify user attributes are properly mapped
- Review logs for detailed error messages

### Testing Service Account Permissions
```bash
# Test with curl to verify permissions
export KC_URL="https://your-keycloak.com"
export REALM="your-realm"
export CLIENT_ID="scim-client"
export CLIENT_SECRET="your-secret"

# Get token
TOKEN=$(curl -s -X POST "$KC_URL/realms/$REALM/protocol/openid-connect/token" \
  -d "client_id=$CLIENT_ID" \
  -d "client_secret=$CLIENT_SECRET" \
  -d "grant_type=client_credentials" | jq -r '.access_token')

# Test user access
curl -H "Authorization: Bearer $TOKEN" \
  "$KC_URL/admin/realms/$REALM/users?max=1"
```

## License

See LICENSE file for details.