from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class KeycloakUser(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    emailVerified: bool = False
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    enabled: bool = True
    attributes: Optional[Dict[str, List[str]]] = None
    
    
class KeycloakGroup(BaseModel):
    id: str
    name: str
    path: str
    attributes: Optional[Dict[str, List[str]]] = None
    subGroupCount: Optional[int] = 0
    subGroups: Optional[List['KeycloakGroup']] = None
    
    
class TokenResponse(BaseModel):
    access_token: str
    expires_in: int
    refresh_expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    scope: Optional[str] = None