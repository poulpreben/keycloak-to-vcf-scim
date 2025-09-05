from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ScimName(BaseModel):
    formatted: Optional[str] = None
    familyName: Optional[str] = None
    givenName: Optional[str] = None
    middleName: Optional[str] = None


class ScimEmail(BaseModel):
    value: str
    type: str = "work"
    primary: bool = True


class ScimUserExtension(BaseModel):
    domain: str


class ScimUser(BaseModel):
    schemas: List[str] = Field(default_factory=lambda: [
        "urn:ietf:params:scim:schemas:core:2.0:User",
        "urn:ietf:params:scim:schemas:extension:ws1b:2.0:User"
    ])
    id: Optional[str] = None
    externalId: str
    userName: str
    name: ScimName
    displayName: str
    active: bool = True
    emails: List[ScimEmail]
    meta: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True
        
    def to_scim_payload(self, include_id: bool = False, for_update: bool = False) -> dict:
        payload = {
            "schemas": self.schemas,
            "userName": self.userName,
            "name": self.name.model_dump(exclude_none=True),
            "displayName": self.displayName,
            "active": self.active,
            "emails": [email.model_dump() for email in self.emails],
            "urn:ietf:params:scim:schemas:extension:ws1b:2.0:User": {
                "domain": self.emails[0].value.split("@")[1] if self.emails else ""
            }
        }
        
        # For updates, include ID but not externalId (can't be changed)
        # For creation, include externalId but not ID
        if for_update and self.id:
            payload["id"] = self.id
            # Don't include externalId in updates
        else:
            payload["externalId"] = self.externalId
            if include_id and self.id:
                payload["id"] = self.id
                
        return payload


class ScimGroup(BaseModel):
    schemas: List[str] = Field(default_factory=lambda: [
        "urn:ietf:params:scim:schemas:core:2.0:Group"
    ])
    id: Optional[str] = None
    externalId: str
    displayName: str
    members: List[Dict[str, str]] = Field(default_factory=list)
    
    class Config:
        populate_by_name = True


class ScimListResponse(BaseModel):
    schemas: List[str] = ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]
    totalResults: int
    startIndex: int
    itemsPerPage: int
    Resources: List[Dict[str, Any]]