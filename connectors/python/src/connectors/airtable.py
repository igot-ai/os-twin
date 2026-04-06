import httpx
from typing import Dict, Any, Optional, List, Union
from urllib.parse import quote
from .base import BaseConnector
from .models import (
    ConnectorConfig,
    ExternalDocument,
    ExternalDocumentList,
    OAuthAuthConfig,
    ConnectorConfigField,
)
from .utils import compute_content_hash, parse_tag_date
from .client import ConnectorHttpClient
from .registry import registry
import logging

logger = logging.getLogger(__name__)

AIRTABLE_API = "https://api.airtable.com/v0"
PAGE_SIZE = 100

def record_to_plain_text(
    fields: Dict[str, Any],
    field_names: Optional[Dict[str, str]] = None
) -> str:
    lines = []
    for key, value in fields.items():
        if value is None:
            continue
        display_name = field_names.get(key, key) if field_names else key
        if isinstance(value, list):
            items = []
            for v in value:
                if isinstance(v, dict):
                    items.append(v.get("url") or v.get("name") or str(v))
                else:
                    items.append(str(v))
            lines.append(f"{display_name}: {', '.join(items)}")
        elif isinstance(value, dict):
            import json
            lines.append(f"{display_name}: {json.dumps(value)}")
        else:
            lines.append(f"{display_name}: {str(value)}")
    return "\n".join(lines)

def extract_title(fields: Dict[str, Any], title_field: Optional[str] = None) -> str:
    if title_field and fields.get(title_field) is not None:
        return str(fields[title_field])
    candidates = ["Name", "Title", "name", "title", "Summary", "summary"]
    for candidate in candidates:
        if fields.get(candidate) is not None:
            return str(fields[candidate])
    for value in fields.values():
        if isinstance(value, str) and value.strip():
            return (value[:80] + "…") if len(value) > 80 else value
    return "Untitled"

def parse_cursor(cursor: Optional[str] = None) -> Optional[str]:
    if not cursor:
        return None
    if cursor.startswith("offset:"):
        return cursor[7:]
    return cursor

@registry.register
class AirtableConnector(BaseConnector):
    @property
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(
            id="airtable",
            name="Airtable",
            description="Sync records from an Airtable table into your knowledge base",
            version="1.0.0",
            icon="airtable",
            auth_config=OAuthAuthConfig(
                mode="oauth",
                provider="airtable",
                required_scopes=["data.records:read", "schema.bases:read"],
            ),
            config_fields=[
                ConnectorConfigField(
                    id="baseSelector",
                    title="Base",
                    type="selector",
                    selector_key="airtable.bases",
                    canonical_param_id="baseId",
                    mode="basic",
                    placeholder="Select a base",
                    required=True,
                ),
                ConnectorConfigField(
                    id="baseId",
                    title="Base ID",
                    type="short-input",
                    canonical_param_id="baseId",
                    mode="advanced",
                    placeholder="e.g. appXXXXXXXXXXXXXX",
                    required=True,
                ),
                ConnectorConfigField(
                    id="tableSelector",
                    title="Table",
                    type="selector",
                    selector_key="airtable.tables",
                    canonical_param_id="tableIdOrName",
                    mode="basic",
                    depends_on=["baseSelector"],
                    placeholder="Select a table",
                    required=True,
                ),
                ConnectorConfigField(
                    id="tableIdOrName",
                    title="Table Name or ID",
                    type="short-input",
                    canonical_param_id="tableIdOrName",
                    mode="advanced",
                    placeholder="e.g. Tasks or tblXXXXXXXXXXXXXX",
                    required=True,
                ),
                ConnectorConfigField(
                    id="viewId",
                    title="View",
                    type="short-input",
                    placeholder="e.g. Grid view or viwXXXXXXXXXXXXXX",
                    required=False,
                ),
                ConnectorConfigField(
                    id="titleField",
                    title="Title Field",
                    type="short-input",
                    placeholder="e.g. Name",
                    required=False,
                ),
                ConnectorConfigField(
                    id="maxRecords",
                    title="Max Records",
                    type="short-input",
                    placeholder="e.g. 1000 (default: unlimited)",
                    required=False,
                ),
            ],
        )

    async def _get_field_names(
        self, client: ConnectorHttpClient, base_id: str, table_id_or_name: str
    ) -> Dict[str, str]:
        field_names = {}
        try:
            url = f"/meta/bases/{base_id}/tables"
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                tables = data.get("tables", [])
                table = next(
                    (t for t in tables if t["id"] == table_id_or_name or t["name"] == table_id_or_name),
                    None
                )
                if table:
                    for field in table.get("fields", []):
                        field_names[field["id"]] = field["name"]
                        field_names[field["name"]] = field["name"]
        except Exception as e:
            logger.warning(f"Error fetching Airtable schema: {e}")
        return field_names

    async def list_documents(
        self, config: Dict[str, Any], cursor: Optional[str] = None
    ) -> ExternalDocumentList:
        access_token = config.get("accessToken")
        base_id = config.get("baseId")
        table_id_or_name = config.get("tableIdOrName")
        view_id = config.get("viewId")
        title_field = config.get("titleField")
        max_records = int(config.get("maxRecords")) if config.get("maxRecords") else 0

        client = ConnectorHttpClient(
            base_url=AIRTABLE_API,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        field_names = await self._get_field_names(client, base_id, table_id_or_name)

        params = {"pageSize": PAGE_SIZE}
        if view_id:
            params["view"] = view_id
        if max_records > 0:
            params["maxRecords"] = max_records
        
        offset = parse_cursor(cursor)
        if offset:
            params["offset"] = offset

        encoded_table = quote(table_id_or_name)
        url = f"/{base_id}/{encoded_table}"
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        records = data.get("records", [])
        documents = []
        for record in records:
            doc = await self._record_to_document(
                record, base_id, table_id_or_name, title_field, field_names
            )
            documents.append(doc)
        
        next_offset = data.get("offset")
        return ExternalDocumentList(
            documents=documents,
            next_cursor=f"offset:{next_offset}" if next_offset else None,
            has_more=bool(next_offset)
        )

    async def get_document(
        self, external_id: str, config: Dict[str, Any]
    ) -> ExternalDocument:
        access_token = config.get("accessToken")
        base_id = config.get("baseId")
        table_id_or_name = config.get("tableIdOrName")
        title_field = config.get("titleField")

        client = ConnectorHttpClient(
            base_url=AIRTABLE_API,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        field_names = await self._get_field_names(client, base_id, table_id_or_name)
        encoded_table = quote(table_id_or_name)
        url = f"/{base_id}/{encoded_table}/{external_id}"
        
        response = await client.get(url)
        if response.status_code in (404, 422):
            raise Exception(f"Document {external_id} not found")
        response.raise_for_status()
        
        record = response.json()
        return await self._record_to_document(
            record, base_id, table_id_or_name, title_field, field_names
        )

    async def _record_to_document(
        self,
        record: Dict[str, Any],
        base_id: str,
        table_id_or_name: str,
        title_field: Optional[str],
        field_names: Dict[str, str]
    ) -> ExternalDocument:
        fields = record.get("fields", {})
        plain_text = record_to_plain_text(fields, field_names)
        content_hash = compute_content_hash(plain_text)
        title = extract_title(fields, title_field)
        
        encoded_table = quote(table_id_or_name)
        source_url = f"https://airtable.com/{base_id}/{encoded_table}/{record['id']}"
        
        return ExternalDocument(
            external_id=record["id"],
            title=title,
            content=plain_text,
            mime_type="text/plain",
            source_url=source_url,
            content_hash=content_hash,
            metadata={"createdTime": record.get("createdTime")}
        )

    async def validate_config(self, config: Dict[str, Any]) -> None:
        access_token = config.get("accessToken")
        base_id = config.get("baseId")
        table_id_or_name = config.get("tableIdOrName")

        if not base_id or not table_id_or_name:
            raise ValueError("Base ID and table name are required")
        
        if not base_id.startswith("app"):
            raise ValueError("Base ID should start with 'app'")
        
        max_records = config.get("maxRecords")
        if max_records:
            try:
                if int(max_records) <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("Max records must be a positive number")

        client = ConnectorHttpClient(
            base_url=AIRTABLE_API,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        encoded_table = quote(table_id_or_name)
        url = f"/{base_id}/{encoded_table}"
        response = await client.get(url, params={"pageSize": 1})
        
        if response.status_code != 200:
            if response.status_code in (404, 422):
                raise ValueError(f"Table '{table_id_or_name}' not found in base '{base_id}'")
            if response.status_code == 403:
                raise ValueError("Access denied. Check your Airtable permissions.")
            raise Exception(f"Airtable API error: {response.status_code} - {response.text}")
        
        view_id = config.get("viewId")
        if view_id:
            response = await client.get(url, params={"pageSize": 1, "view": view_id})
            if response.status_code != 200:
                raise ValueError(f"View '{view_id}' not found in table '{table_id_or_name}'")
