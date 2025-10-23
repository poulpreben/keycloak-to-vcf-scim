from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from src.services.keycloak_client import KeycloakClient
from src.services.scim_client import ScimClient
from src.services.sync_service import SyncService
from src.core.config import Settings, get_settings

debug_router = APIRouter(prefix="/debug", tags=["debug"])


@debug_router.get("/keycloak/users")
async def get_keycloak_users(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Get all users from Keycloak (DEV only)"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    try:
        async with KeycloakClient(settings) as client:
            users = await client.get_users()
            return {
                "total": len(users),
                "users": [
                    {
                        "id": u.id,
                        "username": u.username,
                        "email": u.email,
                        "firstName": u.firstName,
                        "lastName": u.lastName,
                        "enabled": u.enabled
                    } for u in users
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/sync/groups-detail")
async def get_sync_groups_detail(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Get detailed view of groups that will be synced (DEV only)"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    try:
        async with SyncService(settings) as sync_service:
            # Get filtered groups (only subgroups)
            kc_groups, parent_group_map = await sync_service._get_filtered_groups_with_subgroups()
            
            # Get members for each group
            groups_detail = []
            for kc_group in kc_groups:
                members = await sync_service.keycloak_client.get_group_members(kc_group.id)
                parent_group = parent_group_map.get(kc_group.id)
                
                groups_detail.append({
                    "keycloak_name": kc_group.name,
                    "keycloak_path": kc_group.path,
                    "parent_group": parent_group.name if parent_group else None,
                    "scim_name": f"{settings.keycloak_realm}-{parent_group.name if parent_group else 'unknown'}-{kc_group.name}",
                    "member_count": len(members),
                    "members": [
                        {
                            "username": m.username,
                            "email": m.email,
                            "firstName": m.firstName,
                            "lastName": m.lastName
                        } for m in members
                    ]
                })
            
            return {
                "vcenter_filter": settings.vcenter_name,
                "realm": settings.keycloak_realm,
                "total_groups_to_sync": len(kc_groups),
                "groups": groups_detail
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/sync/users-detail")
async def get_sync_users_detail(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Get detailed view of users that will be synced (DEV only)"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    try:
        async with SyncService(settings) as sync_service:
            # Get filtered groups
            kc_groups, parent_group_map = await sync_service._get_filtered_groups_with_subgroups()
            
            # Get all groups for user collection (including parent)
            all_groups_for_users = list(kc_groups) + list(parent_group_map.values())
            
            # Get unique users from all groups
            kc_users = await sync_service._get_users_from_groups(all_groups_for_users)
            
            # Get existing users in SCIM
            existing_users_list = await sync_service.scim_client.list_all_users()
            existing_user_map = {user.get('userName'): user for user in existing_users_list}
            
            # Categorize users
            users_to_create = []
            users_to_update = []
            
            for kc_user in kc_users:
                # Get groups this user belongs to
                user_groups = await sync_service.keycloak_client.get_user_groups(kc_user.id)
                user_group_names = [g.name for g in user_groups]
                
                user_detail = {
                    "username": kc_user.username,
                    "email": kc_user.email,
                    "firstName": kc_user.firstName,
                    "lastName": kc_user.lastName,
                    "enabled": kc_user.enabled,
                    "groups": user_group_names
                }
                
                if kc_user.username in existing_user_map:
                    users_to_update.append(user_detail)
                else:
                    users_to_create.append(user_detail)
            
            return {
                "vcenter_filter": settings.vcenter_name,
                "total_users": len(kc_users),
                "users_to_create_count": len(users_to_create),
                "users_to_update_count": len(users_to_update),
                "users_to_create": users_to_create,
                "users_to_update": users_to_update
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/keycloak/groups/filtered")
async def get_filtered_keycloak_groups(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Get filtered groups from Keycloak (DEV only)"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    try:
        async with KeycloakClient(settings) as client:
            # First get all groups to show what's available
            all_groups = await client.get_groups()
            # Then get filtered groups
            filtered_groups = await client.get_groups(filter_by_vcenter=settings.vcenter_name)
            
            return {
                "vcenter_filter": settings.vcenter_name,
                "vcenter_name_attribute": settings.vcenter_name_attribute,
                "all_groups_count": len(all_groups),
                "filtered_groups_count": len(filtered_groups),
                "all_groups": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "path": g.path,
                        "attributes": g.attributes,
                        "has_vcenter_attr": bool(g.attributes and settings.vcenter_name_attribute in g.attributes)
                    } for g in all_groups
                ],
                "filtered_groups": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "path": g.path,
                        "attributes": g.attributes,
                        "subGroupCount": g.subGroupCount
                    } for g in filtered_groups
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/keycloak/groups")
async def get_keycloak_groups(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Get all groups from Keycloak (DEV only)"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    try:
        async with KeycloakClient(settings) as client:
            groups = await client.get_groups(filter_by_vcenter=settings.vcenter_name)
            return {
                "total": len(groups),
                "groups": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "path": g.path,
                        "attributes": g.attributes,
                        "subGroupCount": g.subGroupCount
                    } for g in groups
                ],
                "vcenter_filter": settings.vcenter_name
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/keycloak/user/{user_id}/groups")
async def get_user_groups(user_id: str, settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Get groups for a specific user (DEV only)"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    try:
        async with KeycloakClient(settings) as client:
            groups = await client.get_user_groups(user_id)
            return {
                "user_id": user_id,
                "total": len(groups),
                "groups": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "path": g.path
                    } for g in groups
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/scim/test-connection")
async def test_scim_connection(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Test connection to SCIM endpoint (DEV only)"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    try:
        async with ScimClient(settings) as client:
            # Try to list users with a small count to test the connection
            result = await client.list_users(count=1)
            return {
                "status": "connected",
                "endpoint": settings.scim_endpoint_url,
                "total_users": result.totalResults
            }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }


@debug_router.get("/scim/users")
async def get_scim_users(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """List users from SCIM endpoint (DEV only)"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    try:
        async with ScimClient(settings) as client:
            result = await client.list_users(count=100)
            return {
                "total": result.totalResults,
                "users": result.Resources
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/scim/groups")
async def get_scim_groups(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """List groups from SCIM endpoint (DEV only)"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    try:
        async with ScimClient(settings) as client:
            all_groups = await client.list_all_groups()
            return {
                "total": len(all_groups),
                "groups": all_groups
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@debug_router.get("/config")
async def get_config(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Get current configuration (DEV only, sensitive data redacted)"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    return {
        "environment": settings.environment,
        "keycloak_url": settings.keycloak_url,
        "keycloak_realm": settings.keycloak_realm,
        "keycloak_client_id": settings.keycloak_client_id,
        "keycloak_client_secret": "***REDACTED***",
        "scim_endpoint_url": settings.scim_endpoint_url,
        "scim_bearer_token": "***REDACTED***",
        "scim_verify_ssl": settings.scim_verify_ssl,
        "vcenter_name": settings.vcenter_name,
        "vcenter_name_attribute": settings.vcenter_name_attribute,
        "sync_interval_minutes": settings.sync_interval_minutes,
        "sync_enabled": settings.sync_enabled,
        "sync_delete_users": settings.sync_delete_users,
        "sync_delete_groups": settings.sync_delete_groups,
        "api_host": settings.api_host,
        "api_port": settings.api_port,
        "api_prefix": settings.api_prefix,
        "log_level": settings.log_level
    }