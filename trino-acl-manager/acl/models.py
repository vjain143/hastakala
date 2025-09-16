from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

Privilege = Literal["SELECT","INSERT","DELETE","UPDATE","OWNERSHIP","GRANT_SELECT","CREATE_VIEW"]

class CatalogAccessControlRule(BaseModel):
    user: Optional[str] = None
    group: Optional[str] = None
    role: Optional[str] = None
    catalog: str
    allow: Literal["all","read-only","none"] = "none"

class CatalogSchemaAccessControlRule(BaseModel):
    user: Optional[str] = None
    group: Optional[str] = None
    role: Optional[str] = None
    catalog: str
    schema: str
    owner: bool = False

class TableAccessControlRule(BaseModel):
    user: Optional[str] = None
    group: Optional[str] = None
    role: Optional[str] = None
    catalog: str
    schema: str
    table: str
    privileges: List[Privilege] = Field(default_factory=list)

class FunctionAccessControlRule(BaseModel):
    user: Optional[str] = None
    group: Optional[str] = None
    role: Optional[str] = None
    catalog: str
    function: str
    execute: bool = True

class ProcedureAccessControlRule(BaseModel):
    user: Optional[str] = None
    group: Optional[str] = None
    role: Optional[str] = None
    catalog: str
    procedure: str
    execute: bool = True

class SessionPropertyAccessControlRule(BaseModel):
    user: Optional[str] = None
    group: Optional[str] = None
    role: Optional[str] = None
    catalog: Optional[str] = None
    property: str
    allow: bool = True

class QueryAccessRule(BaseModel):
    user: Optional[str] = None
    group: Optional[str] = None
    role: Optional[str] = None
    query: Optional[str] = None
    allow: bool = True

class SystemInformationRule(BaseModel):
    user: Optional[str] = None
    group: Optional[str] = None
    role: Optional[str] = None
    allow: bool = True

class ImpersonationRule(BaseModel):
    principal: str
    user: str
    allow: bool = True

class AccessControlRules(BaseModel):
    catalogs: List[CatalogAccessControlRule] = Field(default_factory=list)
    schemas: List[CatalogSchemaAccessControlRule] = Field(default_factory=list)
    tables: List[TableAccessControlRule] = Field(default_factory=list)
    functions: List[FunctionAccessControlRule] = Field(default_factory=list)
    procedures: List[ProcedureAccessControlRule] = Field(default_factory=list)
    session_properties: List[SessionPropertyAccessControlRule] = Field(default_factory=list)
    queries: List[QueryAccessRule] = Field(default_factory=list)
    system_information: List[SystemInformationRule] = Field(default_factory=list)
    impersonation: List[ImpersonationRule] = Field(default_factory=list)

    @staticmethod
    def empty() -> "AccessControlRules":
        return AccessControlRules()
