from typing import List, Optional, Dict, Any, Union, Literal, Annotated
from pydantic import BaseModel, Field, ConfigDict

class OAuthAuthConfig(BaseModel):
    mode: Literal["oauth"]
    provider: str
    required_scopes: Optional[List[str]] = Field(default=None, alias="requiredScopes")

class ApiKeyAuthConfig(BaseModel):
    mode: Literal["apiKey"]
    label: Optional[str] = None
    placeholder: Optional[str] = None

ConnectorAuthConfig = Annotated[Union[OAuthAuthConfig, ApiKeyAuthConfig], Field(discriminator='mode')]

class ExternalDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    external_id: str = Field(alias="externalId")
    title: str
    content: str
    mime_type: str = Field(alias="mimeType")
    source_url: Optional[str] = Field(default=None, alias="sourceUrl")
    content_hash: str = Field(alias="contentHash")
    content_deferred: Optional[bool] = Field(default=False, alias="contentDeferred")
    metadata: Optional[Dict[str, Any]] = None

class ExternalDocumentList(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    documents: List[ExternalDocument]
    next_cursor: Optional[str] = Field(default=None, alias="nextCursor")
    has_more: bool = Field(alias="hasMore")

class SyncResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    docs_added: int = Field(default=0, alias="docsAdded")
    docs_updated: int = Field(default=0, alias="docsUpdated")
    docs_deleted: int = Field(default=0, alias="docsDeleted")
    docs_unchanged: int = Field(default=0, alias="docsUnchanged")
    docs_failed: int = Field(default=0, alias="docsFailed")
    error: Optional[str] = None

class Option(BaseModel):
    label: str
    id: str

class DependsOn(BaseModel):
    all: Optional[List[str]] = None
    any: Optional[List[str]] = None

class ConnectorConfigField(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    type: Literal["short-input", "dropdown", "selector"]
    placeholder: Optional[str] = None
    required: Optional[bool] = True
    description: Optional[str] = None
    options: Optional[List[Option]] = None
    selector_key: Optional[str] = Field(default=None, alias="selectorKey")
    depends_on: Optional[Union[List[str], DependsOn]] = Field(default=None, alias="dependsOn")
    mode: Optional[Literal["basic", "advanced"]] = None
    canonical_param_id: Optional[str] = Field(default=None, alias="canonicalParamId")

class ConnectorConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str
    version: str
    icon: str  # Store icon name/ID as string for serialization
    auth_config: ConnectorAuthConfig = Field(alias="authConfig")
    config_fields: List[ConnectorConfigField] = Field(alias="configFields")
