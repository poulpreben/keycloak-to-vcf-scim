import logging
from typing import List, Dict, Set, Optional
from src.services.keycloak_client import KeycloakClient
from src.services.scim_client import ScimClient
from src.models.keycloak import KeycloakUser, KeycloakGroup
from src.models.scim import ScimUser, ScimName, ScimEmail, ScimGroup
from src.core.config import Settings

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.keycloak_client = KeycloakClient(settings)
        self.scim_client = ScimClient(settings)
        self.sync_stats = {
            "users_created": 0,
            "users_updated": 0,
            "users_deleted": 0,
            "groups_created": 0,
            "groups_deleted": 0,
            "errors": []
        }
        
    async def __aenter__(self):
        await self.keycloak_client.__aenter__()
        await self.scim_client.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.keycloak_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.scim_client.__aexit__(exc_type, exc_val, exc_tb)
        
    def _convert_keycloak_to_scim_user(self, kc_user: KeycloakUser) -> ScimUser:
        """Convert Keycloak user to SCIM user format"""
        return ScimUser(
            externalId=kc_user.id,
            userName=kc_user.username,
            name=ScimName(
                givenName=kc_user.firstName or "",
                familyName=kc_user.lastName or ""
            ),
            displayName=f"{kc_user.firstName or ''} {kc_user.lastName or ''}".strip() or kc_user.username,
            emails=[ScimEmail(value=kc_user.email)] if kc_user.email else [],
            active=kc_user.enabled
        )
        
    def _convert_keycloak_to_scim_group(self, kc_group: KeycloakGroup, parent_group: Optional[KeycloakGroup], members: List[str]) -> ScimGroup:
        """Convert Keycloak group to SCIM group format with custom naming"""
        # Format: {REALM}-{PARENT_GROUP}-{SUBGROUP}
        if parent_group:
            display_name = f"{self.settings.keycloak_realm}-{parent_group.name}-{kc_group.name}"
        else:
            # Fallback if no parent (shouldn't happen with current logic)
            display_name = f"{self.settings.keycloak_realm}-{kc_group.name}"
            
        return ScimGroup(
            externalId=kc_group.id,
            displayName=display_name,
            members=[{"value": member_id, "type": "User"} for member_id in members]
        )
        
    async def _get_filtered_groups_with_subgroups(self) -> tuple[List[KeycloakGroup], Dict[str, KeycloakGroup]]:
        """Get filtered groups and their subgroups
        Returns: (all_groups, parent_group_map)
        """
        all_groups = []
        parent_group_map = {}  # Maps subgroup ID to parent group
        
        # Get top-level groups filtered by vcenter_name
        parent_groups = await self.keycloak_client.get_groups(filter_by_vcenter=self.settings.vcenter_name)
        
        for parent_group in parent_groups:
            # Don't add parent group to sync list, only track it
            
            # Get subgroups if any
            if parent_group.subGroupCount and parent_group.subGroupCount > 0:
                subgroups = await self.keycloak_client.get_subgroups(parent_group.id)
                all_groups.extend(subgroups)
                # Track parent for each subgroup
                for subgroup in subgroups:
                    parent_group_map[subgroup.id] = parent_group
        
        return all_groups, parent_group_map
    
    async def _get_users_from_groups(self, groups: List[KeycloakGroup]) -> List[KeycloakUser]:
        """Get unique users from all groups"""
        user_dict = {}
        
        for group in groups:
            members = await self.keycloak_client.get_group_members(group.id)
            for member in members:
                # Use user ID as key to ensure uniqueness
                user_dict[member.id] = member
        
        return list(user_dict.values())
    
    async def get_sync_preview(self) -> Dict:
        """Get a preview of what would be synced without making changes"""
        try:
            # Get filtered groups from Keycloak (only subgroups)
            kc_groups, parent_group_map = await self._get_filtered_groups_with_subgroups()

            # Get unique users from all filtered groups (including parent for user collection)
            all_groups_for_users = list(kc_groups) + list(parent_group_map.values())
            kc_users = await self._get_users_from_groups(all_groups_for_users)

            # Get existing users in SCIM endpoint with pagination
            existing_users_list = await self.scim_client.list_all_users()
            existing_usernames = {user.get('userName') for user in existing_users_list}

            # Get existing groups from SCIM
            existing_groups_list = await self.scim_client.list_all_groups()
            existing_groups_map = {g.get('displayName'): g for g in existing_groups_list}

            # Track which groups exist in Keycloak
            synced_group_names = set()
            for kc_group in kc_groups:
                parent_group = parent_group_map.get(kc_group.id)
                display_name = f"{self.settings.keycloak_realm}-{parent_group.name if parent_group else 'unknown'}-{kc_group.name}"
                synced_group_names.add(display_name)

            # Determine sync actions
            users_to_create = []
            users_to_update = []
            users_to_delete = []
            groups_to_delete = []

            for kc_user in kc_users:
                if kc_user.username not in existing_usernames:
                    users_to_create.append({
                        "username": kc_user.username,
                        "email": kc_user.email,
                        "firstName": kc_user.firstName,
                        "lastName": kc_user.lastName,
                        "enabled": kc_user.enabled
                    })
                else:
                    users_to_update.append({
                        "username": kc_user.username,
                        "email": kc_user.email,
                        "firstName": kc_user.firstName,
                        "lastName": kc_user.lastName,
                        "enabled": kc_user.enabled
                    })

            # Determine users to delete if enabled
            if self.settings.sync_delete_users:
                kc_usernames = {u.username for u in kc_users}
                for existing_user in existing_users_list:
                    if existing_user.get('userName') not in kc_usernames:
                        users_to_delete.append({
                            "username": existing_user.get('userName'),
                            "id": existing_user.get('id')
                        })

            # Determine groups to delete if enabled
            if self.settings.sync_delete_groups:
                realm_prefix = f"{self.settings.keycloak_realm}-"
                for display_name, scim_group in existing_groups_map.items():
                    if display_name.startswith(realm_prefix) and display_name not in synced_group_names:
                        groups_to_delete.append({
                            "displayName": display_name,
                            "id": scim_group.get('id')
                        })

            return {
                "users_to_create": users_to_create,
                "users_to_update": users_to_update,
                "users_to_delete": users_to_delete,
                "groups_to_sync": [
                    {
                        "name": g.name,
                        "path": g.path,
                        "scim_name": f"{self.settings.keycloak_realm}-{parent_group_map.get(g.id).name if g.id in parent_group_map else 'unknown'}-{g.name}"
                    } for g in kc_groups
                ],
                "groups_to_delete": groups_to_delete,
                "total_filtered_users": len(kc_users),
                "total_scim_users": len(existing_users_list),
                "total_filtered_groups": len(kc_groups),
                "total_scim_groups": len(existing_groups_list),
                "vcenter_filter": self.settings.vcenter_name,
                "delete_users_enabled": self.settings.sync_delete_users,
                "delete_groups_enabled": self.settings.sync_delete_groups
            }
        except Exception as e:
            logger.error(f"Failed to generate sync preview: {e}")
            return {"error": str(e)}
            
    async def sync_users(self) -> Dict:
        """Sync users from Keycloak to vCenter"""
        self.sync_stats = {
            "users_created": 0,
            "users_updated": 0,
            "users_deleted": 0,
            "groups_created": 0,
            "groups_deleted": 0,
            "errors": []
        }
        
        try:
            # Get filtered groups from Keycloak (only subgroups)
            logger.info(f"Fetching groups filtered by vcenter_name: {self.settings.vcenter_name}...")
            kc_groups, parent_group_map = await self._get_filtered_groups_with_subgroups()
            logger.info(f"Found {len(kc_groups)} subgroups to sync")
            
            # Get unique users from filtered groups (including parent for user collection)
            logger.info("Fetching users from filtered groups...")
            all_groups_for_users = list(kc_groups) + list(parent_group_map.values())
            kc_users = await self._get_users_from_groups(all_groups_for_users)
            logger.info(f"Found {len(kc_users)} unique users in filtered groups")
            
            # Get existing users in SCIM endpoint with pagination
            logger.info("Fetching existing users from SCIM endpoint...")
            existing_users_list = await self.scim_client.list_all_users()
            existing_user_map = {user.get('userName'): user for user in existing_users_list}
            
            # Sync each user
            for kc_user in kc_users:
                try:
                    scim_user = self._convert_keycloak_to_scim_user(kc_user)
                    existing_user = existing_user_map.get(kc_user.username)
                    
                    if existing_user:
                        # Update existing user - check if update is needed
                        user_id = existing_user.get('id')
                        existing_external_id = existing_user.get('externalId')
                        
                        # Check if the externalId matches (if not, we have a different user with same username)
                        if existing_external_id != kc_user.id:
                            logger.warning(f"User {kc_user.username} exists with different externalId: {existing_external_id} vs {kc_user.id}")
                            # For now, skip this user to avoid conflicts
                            continue
                        
                        if user_id:
                            # Preserve the SCIM ID and externalId for update
                            scim_user.id = user_id
                            result = await self.scim_client.update_user(user_id, scim_user)
                            if result:
                                self.sync_stats["users_updated"] += 1
                                logger.info(f"Updated user {kc_user.username}")
                            else:
                                self.sync_stats["errors"].append(f"Failed to update user {kc_user.username}")
                    else:
                        # Create new user
                        result = await self.scim_client.create_user(scim_user)
                        if result:
                            self.sync_stats["users_created"] += 1
                        else:
                            self.sync_stats["errors"].append(f"Failed to create user {kc_user.username}")
                            
                except Exception as e:
                    error_msg = f"Error syncing user {kc_user.username}: {str(e)}"
                    logger.error(error_msg)
                    self.sync_stats["errors"].append(error_msg)
                    
            # Handle deletions (users in SCIM but not in Keycloak filtered groups)
            if self.settings.sync_delete_users:
                kc_usernames = {u.username for u in kc_users}
                for scim_username, scim_user in existing_user_map.items():
                    if scim_username not in kc_usernames:
                        user_id = scim_user.get('id')
                        if user_id:
                            try:
                                success = await self.scim_client.delete_user(user_id)
                                if success:
                                    self.sync_stats["users_deleted"] += 1
                                    logger.info(f"Deleted user {scim_username} from SCIM endpoint")
                                else:
                                    self.sync_stats["errors"].append(f"Failed to delete user {scim_username}")
                            except Exception as e:
                                error_msg = f"Error deleting user {scim_username}: {str(e)}"
                                logger.error(error_msg)
                                self.sync_stats["errors"].append(error_msg)
            else:
                # Just log users that would be deleted
                kc_usernames = {u.username for u in kc_users}
                for scim_username, scim_user in existing_user_map.items():
                    if scim_username not in kc_usernames:
                        logger.info(f"User {scim_username} exists in SCIM endpoint but not in Keycloak (deletion disabled)")
                    
            logger.info(f"User sync completed: {self.sync_stats}")
            return self.sync_stats
            
        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            logger.error(error_msg)
            self.sync_stats["errors"].append(error_msg)
            return self.sync_stats
            
    async def sync_groups(self) -> Dict:
        """Sync filtered groups from Keycloak (only subgroups) and their memberships"""
        try:
            # Get filtered groups from Keycloak (only subgroups)
            logger.info(f"Fetching groups filtered by vcenter_name: {self.settings.vcenter_name}...")
            kc_groups, parent_group_map = await self._get_filtered_groups_with_subgroups()
            logger.info(f"Found {len(kc_groups)} subgroups to sync")

            # Get existing groups from SCIM
            logger.info("Fetching existing groups from SCIM endpoint...")
            existing_groups_list = await self.scim_client.list_all_groups()
            existing_groups_map = {g.get('displayName'): g for g in existing_groups_list}

            # Get all users from SCIM to map Keycloak IDs to SCIM IDs
            logger.info("Fetching users from SCIM for ID mapping...")
            scim_users = await self.scim_client.list_all_users()
            # Map Keycloak user IDs (externalId) to SCIM user IDs
            kc_to_scim_user_map = {}
            for user in scim_users:
                external_id = user.get('externalId')
                scim_id = user.get('id')
                if external_id and scim_id:
                    kc_to_scim_user_map[external_id] = scim_id

            # Track which groups we've synced from Keycloak
            synced_group_names = set()

            # For each subgroup, create or update it
            for kc_group in kc_groups:
                try:
                    parent_group = parent_group_map.get(kc_group.id)
                    display_name = f"{self.settings.keycloak_realm}-{parent_group.name if parent_group else 'unknown'}-{kc_group.name}"
                    synced_group_names.add(display_name)

                    existing_group = existing_groups_map.get(display_name)

                    if existing_group:
                        group_scim_id = existing_group.get('id')
                        logger.info(f"Group {display_name} already exists with ID {group_scim_id}")
                    else:
                        # Create group without members initially
                        scim_group = self._convert_keycloak_to_scim_group(kc_group, parent_group, [])
                        result = await self.scim_client.create_group(scim_group)
                        if result:
                            self.sync_stats["groups_created"] += 1
                            group_scim_id = result.id
                            logger.info(f"Created group {display_name} with ID {group_scim_id}")
                        else:
                            self.sync_stats["errors"].append(f"Failed to create group {display_name}")
                            continue

                    # Now update group membership
                    if group_scim_id:
                        # Get members from Keycloak
                        kc_members = await self.keycloak_client.get_group_members(kc_group.id)

                        # Convert Keycloak user IDs to SCIM user IDs
                        scim_member_ids = []
                        for member in kc_members:
                            scim_id = kc_to_scim_user_map.get(member.id)
                            if scim_id:
                                scim_member_ids.append(scim_id)
                            else:
                                logger.warning(f"User {member.username} ({member.id}) not found in SCIM")

                        # Replace all group members (this handles add/remove in one operation)
                        success = await self.scim_client.replace_group_members(group_scim_id, scim_member_ids)
                        if success:
                            logger.info(f"Updated group {display_name} with {len(scim_member_ids)} members")
                        else:
                            self.sync_stats["errors"].append(f"Failed to update members for group {display_name}")

                except Exception as e:
                    error_msg = f"Error syncing group {kc_group.name}: {str(e)}"
                    logger.error(error_msg)
                    self.sync_stats["errors"].append(error_msg)

            # Handle group deletions (groups in SCIM that match naming convention but not in Keycloak)
            if self.settings.sync_delete_groups:
                # Parse the naming convention to identify groups to potentially delete
                realm_prefix = f"{self.settings.keycloak_realm}-"

                for display_name, scim_group in existing_groups_map.items():
                    # Check if this group follows our naming convention
                    if display_name.startswith(realm_prefix):
                        # Check if this group was NOT synced from Keycloak
                        if display_name not in synced_group_names:
                            group_id = scim_group.get('id')
                            if group_id:
                                try:
                                    success = await self.scim_client.delete_group(group_id)
                                    if success:
                                        self.sync_stats["groups_deleted"] += 1
                                        logger.info(f"Deleted group {display_name} from SCIM endpoint")
                                    else:
                                        self.sync_stats["errors"].append(f"Failed to delete group {display_name}")
                                except Exception as e:
                                    error_msg = f"Error deleting group {display_name}: {str(e)}"
                                    logger.error(error_msg)
                                    self.sync_stats["errors"].append(error_msg)
            else:
                # Just log groups that would be deleted
                realm_prefix = f"{self.settings.keycloak_realm}-"
                for display_name, scim_group in existing_groups_map.items():
                    if display_name.startswith(realm_prefix) and display_name not in synced_group_names:
                        logger.info(f"Group {display_name} exists in SCIM endpoint but not in Keycloak (deletion disabled)")

            return self.sync_stats

        except Exception as e:
            error_msg = f"Group sync failed: {str(e)}"
            logger.error(error_msg)
            self.sync_stats["errors"].append(error_msg)
            return self.sync_stats
            
    async def full_sync(self) -> Dict:
        """Perform full sync of users and groups"""
        logger.info("Starting full sync...")
        await self.sync_users()
        await self.sync_groups()
        logger.info(f"Full sync completed: {self.sync_stats}")
        return self.sync_stats