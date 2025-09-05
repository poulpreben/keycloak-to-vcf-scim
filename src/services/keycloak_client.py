import httpx
from typing import List, Optional
import logging
from src.models.keycloak import KeycloakUser, KeycloakGroup, TokenResponse
from src.core.config import Settings

logger = logging.getLogger(__name__)


class KeycloakClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        self.token_url = f"{self.base_url}/protocol/openid-connect/token"
        self.admin_url = f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}"
        self.client = httpx.AsyncClient()
        self.access_token: Optional[str] = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        
    async def get_access_token(self) -> str:
        """Get access token using client credentials flow"""
        try:
            response = await self.client.post(
                self.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.settings.keycloak_client_id,
                    "client_secret": self.settings.keycloak_client_secret
                }
            )
            response.raise_for_status()
            token_data = TokenResponse(**response.json())
            self.access_token = token_data.access_token
            return self.access_token
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get access token: {e}")
            raise
            
    async def ensure_authenticated(self):
        """Ensure we have a valid access token"""
        if not self.access_token:
            await self.get_access_token()
            
    async def get_users(self) -> List[KeycloakUser]:
        """Get all users from Keycloak"""
        await self.ensure_authenticated()
        
        try:
            response = await self.client.get(
                f"{self.admin_url}/users",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"max": 10000}  # Adjust as needed
            )
            response.raise_for_status()
            users_data = response.json()
            return [KeycloakUser(**user) for user in users_data]
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get users: {e}")
            raise
            
    async def get_user_groups(self, user_id: str) -> List[KeycloakGroup]:
        """Get groups for a specific user"""
        await self.ensure_authenticated()
        
        try:
            response = await self.client.get(
                f"{self.admin_url}/users/{user_id}/groups",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            response.raise_for_status()
            groups_data = response.json()
            return [KeycloakGroup(**group) for group in groups_data]
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get user groups: {e}")
            raise
            
    async def get_group_details(self, group_id: str) -> KeycloakGroup:
        """Get detailed information about a specific group including attributes"""
        await self.ensure_authenticated()
        
        try:
            response = await self.client.get(
                f"{self.admin_url}/groups/{group_id}",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            response.raise_for_status()
            return KeycloakGroup(**response.json())
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get group details for {group_id}: {e}")
            raise
    
    async def get_groups(self, filter_by_vcenter: Optional[str] = None) -> List[KeycloakGroup]:
        """Get all groups from Keycloak, optionally filtered by vcenter_name attribute"""
        await self.ensure_authenticated()
        
        try:
            response = await self.client.get(
                f"{self.admin_url}/groups",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"max": 10000, "briefRepresentation": False}
            )
            response.raise_for_status()
            groups_data = response.json()
            
            # Fetch detailed info for each group to get attributes
            all_groups = []
            for group_data in groups_data:
                detailed_group = await self.get_group_details(group_data['id'])
                all_groups.append(detailed_group)
            
            if not filter_by_vcenter:
                return all_groups
            
            # Filter groups that have the vcenter_name attribute matching our filter
            logger.info(f"Filtering groups by {self.settings.vcenter_name_attribute}={filter_by_vcenter}")
            filtered_groups = []
            for group in all_groups:
                if group.attributes and self.settings.vcenter_name_attribute in group.attributes:
                    vcenter_values = group.attributes[self.settings.vcenter_name_attribute]
                    logger.debug(f"Group {group.name} has {self.settings.vcenter_name_attribute}={vcenter_values}")
                    if filter_by_vcenter in vcenter_values:
                        logger.info(f"Group {group.name} matches filter")
                        filtered_groups.append(group)
                    else:
                        logger.debug(f"Group {group.name} does not match filter")
                else:
                    logger.debug(f"Group {group.name} has no {self.settings.vcenter_name_attribute} attribute")
            
            logger.info(f"Filtered {len(filtered_groups)} groups from {len(all_groups)} total groups")
            return filtered_groups
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get groups: {e}")
            raise
    
    async def get_subgroups(self, group_id: str) -> List[KeycloakGroup]:
        """Get subgroups of a specific group"""
        await self.ensure_authenticated()
        
        try:
            response = await self.client.get(
                f"{self.admin_url}/groups/{group_id}/children",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"max": 10000}
            )
            response.raise_for_status()
            groups_data = response.json()
            return [KeycloakGroup(**group) for group in groups_data]
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get subgroups: {e}")
            raise
            
    async def get_group_members(self, group_id: str) -> List[KeycloakUser]:
        """Get members of a specific group"""
        await self.ensure_authenticated()
        
        try:
            response = await self.client.get(
                f"{self.admin_url}/groups/{group_id}/members",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params={"max": 10000}
            )
            response.raise_for_status()
            members_data = response.json()
            return [KeycloakUser(**member) for member in members_data]
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get group members: {e}")
            raise