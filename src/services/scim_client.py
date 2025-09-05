import httpx
from typing import List, Optional, Dict, Any
import logging
from src.models.scim import ScimUser, ScimGroup, ScimListResponse
from src.core.config import Settings

logger = logging.getLogger(__name__)


class ScimClient:
    def __init__(self, settings: Settings):
        self.scim_url = settings.scim_endpoint_url
        self.bearer_token = settings.scim_bearer_token
        self.client = httpx.AsyncClient(verify=settings.scim_verify_ssl)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for SCIM requests"""
        return {
            "Content-Type": "application/scim+json",
            "Authorization": f"Bearer {self.bearer_token}"
        }
        
    async def create_user(self, user: ScimUser) -> Optional[ScimUser]:
        """Create a user via SCIM"""
        try:
            response = await self.client.post(
                f"{self.scim_url}/Users",
                headers=self._get_headers(),
                json=user.to_scim_payload()
            )
            response.raise_for_status()
            created_user = ScimUser(**response.json())
            logger.info(f"Created user: {user.userName}")
            return created_user
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to create user {user.userName}: {e}")
            if e.response:
                logger.error(f"Response body: {e.response.text}")
            return None
            
    async def get_user(self, username: str) -> Optional[ScimUser]:
        """Get a user by username"""
        try:
            response = await self.client.get(
                f"{self.scim_url}/Users",
                headers=self._get_headers(),
                params={
                    "filter": f'userName eq "{username}"',
                    "startIndex": 1,
                    "count": 1
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('totalResults', 0) > 0:
                resources = data.get('Resources', [])
                if resources:
                    return ScimUser(**resources[0])
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get user {username}: {e}")
            return None
            
    async def update_user(self, user_id: str, user: ScimUser) -> Optional[ScimUser]:
        """Update a user via SCIM"""
        try:
            # Set the ID for the update payload
            user.id = user_id
            response = await self.client.put(
                f"{self.scim_url}/Users/{user_id}",
                headers=self._get_headers(),
                json=user.to_scim_payload(for_update=True)
            )
            response.raise_for_status()
            updated_user = ScimUser(**response.json())
            logger.info(f"Updated user: {user.userName}")
            return updated_user
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to update user {user.userName}: {e}")
            if e.response:
                logger.error(f"Response body: {e.response.text}")
            return None
            
    async def delete_user(self, user_id: str) -> bool:
        """Delete a user via SCIM"""
        try:
            response = await self.client.delete(
                f"{self.scim_url}/Users/{user_id}",
                headers=self._get_headers()
            )
            response.raise_for_status()
            logger.info(f"Deleted user with ID: {user_id}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to delete user {user_id}: {e}")
            return False
            
    async def list_users(self, start_index: int = 1, count: int = 100) -> ScimListResponse:
        """List all users via SCIM"""
        try:
            response = await self.client.get(
                f"{self.scim_url}/Users",
                headers=self._get_headers(),
                params={
                    "startIndex": start_index,
                    "count": count
                }
            )
            response.raise_for_status()
            return ScimListResponse(**response.json())
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list users: {e}")
            return ScimListResponse(totalResults=0, startIndex=1, itemsPerPage=0, Resources=[])
    
    async def list_all_users(self) -> List[Dict[str, Any]]:
        """List all users via SCIM with pagination"""
        all_users = []
        start_index = 1
        page_size = 100  # Use smaller page size
        
        while True:
            try:
                response = await self.list_users(start_index, page_size)
                all_users.extend(response.Resources)
                
                # Check if we've retrieved all users
                if start_index + len(response.Resources) > response.totalResults:
                    break
                    
                # No more results
                if len(response.Resources) < page_size:
                    break
                    
                start_index += page_size
                
            except Exception as e:
                logger.error(f"Error during pagination at index {start_index}: {e}")
                break
                
        return all_users
            
    async def list_groups(self, start_index: int = 1, count: int = 100) -> ScimListResponse:
        """List all groups via SCIM"""
        try:
            response = await self.client.get(
                f"{self.scim_url}/Groups",
                headers=self._get_headers(),
                params={
                    "startIndex": start_index,
                    "count": count
                }
            )
            response.raise_for_status()
            return ScimListResponse(**response.json())
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list groups: {e}")
            return ScimListResponse(totalResults=0, startIndex=1, itemsPerPage=0, Resources=[])
    
    async def list_all_groups(self) -> List[Dict[str, Any]]:
        """List all groups via SCIM with pagination"""
        all_groups = []
        start_index = 1
        page_size = 100
        
        while True:
            try:
                response = await self.list_groups(start_index, page_size)
                all_groups.extend(response.Resources)
                
                if start_index + len(response.Resources) > response.totalResults:
                    break
                    
                if len(response.Resources) < page_size:
                    break
                    
                start_index += page_size
                
            except Exception as e:
                logger.error(f"Error during group pagination at index {start_index}: {e}")
                break
                
        return all_groups
    
    async def patch_group_members(self, group_id: str, member_ids: List[str], operation: str = "add") -> bool:
        """Add or remove members from a group using PATCH"""
        try:
            operations = []
            for member_id in member_ids:
                operations.append({
                    "op": operation,
                    "path": "members",
                    "value": [{
                        "value": member_id,
                        "type": "User"
                    }]
                })
            
            patch_data = {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": operations
            }
            
            response = await self.client.patch(
                f"{self.scim_url}/Groups/{group_id}",
                headers=self._get_headers(),
                json=patch_data
            )
            response.raise_for_status()
            logger.info(f"Updated group members for group {group_id}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to update group members: {e}")
            if e.response:
                logger.error(f"Response body: {e.response.text}")
            return False
    
    async def create_group(self, group: ScimGroup) -> Optional[ScimGroup]:
        """Create a group via SCIM"""
        try:
            response = await self.client.post(
                f"{self.scim_url}/Groups",
                headers=self._get_headers(),
                json=group.model_dump(exclude_none=True)
            )
            response.raise_for_status()
            created_group = ScimGroup(**response.json())
            logger.info(f"Created group: {group.displayName}")
            return created_group
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to create group {group.displayName}: {e}")
            if e.response:
                logger.error(f"Response body: {e.response.text}")
            return None
            
    async def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Get a group by ID including members"""
        try:
            response = await self.client.get(
                f"{self.scim_url}/Groups/{group_id}",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get group {group_id}: {e}")
            return None
    
    async def replace_group_members(self, group_id: str, member_ids: List[str]) -> bool:
        """Replace all members of a group"""
        try:
            # Use replace operation to set exact membership
            patch_data = {
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
                "Operations": [
                    {
                        "op": "replace",
                        "path": "members",
                        "value": [{"value": mid, "type": "User"} for mid in member_ids] if member_ids else []
                    }
                ]
            }
            
            response = await self.client.patch(
                f"{self.scim_url}/Groups/{group_id}",
                headers=self._get_headers(),
                json=patch_data
            )
            response.raise_for_status()
            logger.info(f"Replaced group members for group {group_id}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to replace group members: {e}")
            if e.response:
                logger.error(f"Response body: {e.response.text}")
            return False
    
    async def delete_group(self, group_id: str) -> bool:
        """Delete a group via SCIM"""
        try:
            response = await self.client.delete(
                f"{self.scim_url}/Groups/{group_id}",
                headers=self._get_headers()
            )
            response.raise_for_status()
            logger.info(f"Deleted group with ID: {group_id}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to delete group {group_id}: {e}")
            return False