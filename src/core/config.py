from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, Literal
from functools import lru_cache
from urllib.parse import urlparse


class Settings(BaseSettings):
    environment: Literal["DEV", "PROD"] = Field(default="PROD", description="Environment mode")
    
    # Keycloak OAuth2/OIDC settings
    keycloak_url: str = Field(..., description="Keycloak server URL")
    keycloak_realm: str = Field(..., description="Keycloak realm")
    keycloak_client_id: str = Field(..., description="OAuth2 client ID")
    keycloak_client_secret: str = Field(..., description="OAuth2 client secret")
    
    # SCIM Endpoint settings
    scim_endpoint_url: str = Field(..., description="SCIM 2.0 endpoint URL")
    scim_bearer_token: str = Field(..., description="Bearer token for SCIM authentication")
    scim_verify_ssl: bool = Field(default=True, description="Verify SSL certificates for SCIM endpoint")
    
    # vCenter filtering settings
    vcenter_name: Optional[str] = Field(
        None, description="vCenter name to filter groups (e.g., vcenter01.contoso.com)"
    )
    vcenter_name_attribute: str = Field(default="vcenter_name", description="Attribute name in Keycloak groups for vCenter filtering")
    
    # Sync settings
    sync_interval_minutes: int = Field(default=60, description="Sync interval in minutes")
    sync_enabled: bool = Field(default=True, description="Enable automatic sync")
    sync_delete_users: bool = Field(default=False, description="Delete users in SCIM that are not in Keycloak filtered groups")
    
    # API settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_prefix: str = Field(default="/api", description="API prefix")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @validator('vcenter_name', always=True)
    def extract_vcenter_name(cls, v, values):
        """Extract vCenter name from SCIM URL if not explicitly provided"""
        if v:
            return v
        
        # Try to extract from SCIM endpoint URL
        scim_url = values.get('scim_endpoint_url')
        if scim_url:
            parsed = urlparse(scim_url)
            hostname = parsed.hostname
            if hostname:
                # Return the full hostname as vcenter_name
                return hostname
        
        return None


@lru_cache()
def get_settings() -> Settings:
    return Settings()