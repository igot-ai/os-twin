import httpx
import logging
import asyncio
from typing import Dict, Any, Optional, List, Union
from .base import BaseConnector
from .models import (
    ConnectorConfig,
    ExternalDocument,
    ExternalDocumentList,
    OAuthAuthConfig,
    ConnectorConfigField,
    Option,
)
from .utils import compute_content_hash, parse_tag_date
from .client import ConnectorHttpClient
from .registry import registry

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hubapi.com"
PAGE_SIZE = 100

OBJECT_PROPERTIES = {
    "contacts": [
        "firstname", "lastname", "email", "phone", "company", "jobtitle",
        "lifecyclestage", "hs_lead_status", "hubspot_owner_id", "createdate",
        "lastmodifieddate",
    ],
    "companies": [
        "name", "domain", "industry", "description", "phone", "city", "state",
        "country", "numberofemployees", "annualrevenue", "hubspot_owner_id",
        "createdate", "hs_lastmodifieddate",
    ],
    "deals": [
        "dealname", "amount", "dealstage", "pipeline", "closedate",
        "hubspot_owner_id", "createdate", "hs_lastmodifieddate",
    ],
    "tickets": [
        "subject", "content", "hs_pipeline", "hs_pipeline_stage",
        "hs_ticket_priority", "hubspot_owner_id", "createdate",
        "hs_lastmodifieddate",
    ],
}

def build_record_title(object_type: str, properties: Dict[str, Any]) -> str:
    if object_type == "contacts":
        first = properties.get("firstname") or ""
        last = properties.get("lastname") or ""
        name = f"{first} {last}".strip()
        return name or properties.get("email") or "Unnamed Contact"
    elif object_type == "companies":
        return properties.get("name") or properties.get("domain") or "Unnamed Company"
    elif object_type == "deals":
        return properties.get("dealname") or "Unnamed Deal"
    elif object_type == "tickets":
        return properties.get("subject") or "Unnamed Ticket"
    else:
        return f"Record {properties.get('hs_object_id', 'Unknown')}"

def build_record_content(object_type: str, properties: Dict[str, Any]) -> str:
    parts = []
    title = build_record_title(object_type, properties)
    parts.append(title)

    for key, value in properties.items():
        if value and key != "hs_object_id":
            label = key.replace("_", " ").title()
            parts.append(f"{label}: {value}")
    
    return "\n".join(parts).strip()

async def get_portal_id(client: ConnectorHttpClient, config: Dict[str, Any]) -> str:
    if config.get("portalId"):
        return config["portalId"]
    
    response = await client.get("/account-info/v3/details")
    response.raise_for_status()
    data = response.json()
    portal_id = str(data["portalId"])
    config["portalId"] = portal_id
    return portal_id

def record_to_document(
    record: Dict[str, Any],
    object_type: str,
    portal_id: str
) -> ExternalDocument:
    id = record["id"]
    properties = record.get("properties", {})
    
    content = build_record_content(object_type, properties)
    content_hash = compute_content_hash(content)
    title = build_record_title(object_type, properties)
    
    last_modified = (
        properties.get("lastmodifieddate") or 
        properties.get("hs_lastmodifieddate") or 
        properties.get("createdate")
    )
    
    return ExternalDocument(
        external_id=id,
        title=title,
        content=content,
        mime_type="text/plain",
        source_url=f"https://app.hubspot.com/contacts/{portal_id}/record/{object_type}/{id}",
        content_hash=content_hash,
        metadata={
            "objectType": object_type,
            "owner": properties.get("hubspot_owner_id"),
            "lastModified": last_modified,
            "pipeline": properties.get("pipeline") or properties.get("hs_pipeline")
        }
    )

@registry.register
class HubSpotConnector(BaseConnector):
    @property
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(
            id="hubspot",
            name="HubSpot",
            description="Sync CRM records from HubSpot into your knowledge base",
            version="1.0.0",
            icon="hubspot",
            auth_config=OAuthAuthConfig(
                mode="oauth",
                provider="hubspot",
                required_scopes=[
                    "crm.objects.contacts.read",
                    "crm.objects.companies.read",
                    "crm.objects.deals.read",
                    "tickets",
                ],
            ),
            config_fields=[
                ConnectorConfigField(
                    id="objectType",
                    title="Object Type",
                    type="dropdown",
                    required=True,
                    options=[
                        Option(label="Contacts", id="contacts"),
                        Option(label="Companies", id="companies"),
                        Option(label="Deals", id="deals"),
                        Option(label="Tickets", id="tickets"),
                    ],
                ),
                ConnectorConfigField(
                    id="maxRecords",
                    title="Max Records",
                    type="short-input",
                    required=False,
                    placeholder="e.g. 500 (default: unlimited)",
                ),
            ],
        )

    def _get_client(self, access_token: str) -> ConnectorHttpClient:
        return ConnectorHttpClient(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )

    async def list_documents(
        self, config: Dict[str, Any], cursor: Optional[str] = None
    ) -> ExternalDocumentList:
        access_token = config.get("accessToken")
        object_type = config.get("objectType")
        max_records = int(config.get("maxRecords")) if config.get("maxRecords") else 0
        properties = OBJECT_PROPERTIES.get(object_type, [])
        
        client = self._get_client(access_token)
        portal_id = await get_portal_id(client, config)
        
        sort_property = "lastmodifieddate" if object_type == "contacts" else "hs_lastmodifieddate"
        
        search_body = {
            "properties": properties,
            "sorts": [{"propertyName": sort_property, "direction": "DESCENDING"}],
            "limit": PAGE_SIZE,
        }
        if cursor:
            search_body["after"] = cursor
        
        response = await client.post(f"/crm/v3/objects/{object_type}/search", json=search_body)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        paging = data.get("paging", {})
        next_cursor = paging.get("next", {}).get("after")
        
        documents = [record_to_document(r, object_type, portal_id) for r in results]
        
        previously_fetched = config.get("totalDocsFetched", 0)
        if max_records > 0:
            remaining = max_records - previously_fetched
            if len(documents) > remaining:
                documents = documents[:remaining]
        
        total_fetched = previously_fetched + len(documents)
        config["totalDocsFetched"] = total_fetched
        
        has_more = bool(next_cursor) and (max_records <= 0 or total_fetched < max_records)
        
        return ExternalDocumentList(
            documents=documents,
            next_cursor=next_cursor if has_more else None,
            has_more=has_more
        )

    async def get_document(
        self, external_id: str, config: Dict[str, Any]
    ) -> ExternalDocument:
        access_token = config.get("accessToken")
        object_type = config.get("objectType")
        properties = OBJECT_PROPERTIES.get(object_type, [])
        
        client = self._get_client(access_token)
        portal_id = await get_portal_id(client, config)
        
        params = [("properties", prop) for prop in properties]
        response = await client.get(f"/crm/v3/objects/{object_type}/{external_id}", params=params)
        if response.status_code == 404:
            raise Exception(f"HubSpot {object_type} {external_id} not found")
        response.raise_for_status()
        
        record = response.json()
        return record_to_document(record, object_type, portal_id)

    async def validate_config(self, config: Dict[str, Any]) -> None:
        access_token = config.get("accessToken")
        object_type = config.get("objectType")
        
        if not object_type:
            raise ValueError("Object type is required")
        if object_type not in OBJECT_PROPERTIES:
            raise ValueError(f"Unsupported object type: {object_type}")
        
        max_records = config.get("maxRecords")
        if max_records:
            try:
                if int(max_records) <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("Max records must be a positive number")

        client = self._get_client(access_token)
        response = await client.get(f"/crm/v3/objects/{object_type}", params={"limit": 1})
        if response.status_code != 200:
            raise Exception(f"Failed to access HubSpot {object_type}: {response.status_code} - {response.text}")
