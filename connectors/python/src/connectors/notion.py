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
from .utils import join_tag_array, parse_tag_date
from .client import ConnectorHttpClient
from .registry import registry

logger = logging.getLogger(__name__)

NOTION_API_VERSION = "2022-06-28"
NOTION_BASE_URL = "https://api.notion.com/v1"

def extract_title(properties: Dict[str, Any]) -> str:
    for value in properties.values():
        if not isinstance(value, dict):
            continue
        if value.get("type") == "title" and isinstance(value.get("title"), list) and value["title"]:
            return "".join(t.get("plain_text", "") for t in value["title"])
    return "Untitled"

def rich_text_to_plain(rich_text: List[Dict[str, Any]]) -> str:
    return "".join(t.get("plain_text", "") for t in rich_text)

def blocks_to_plain_text(blocks: List[Dict[str, Any]]) -> str:
    lines = []
    for block in blocks:
        block_type = block.get("type")
        if not block_type:
            continue
        block_data = block.get(block_type)
        if not isinstance(block_data, dict):
            continue

        if block_type == "code":
            rich_text = block_data.get("rich_text", [])
            language = block_data.get("language", "")
            code = rich_text_to_plain(rich_text)
            lines.append(f"```{language}\n{code}\n```" if language else f"```\n{code}\n```")
        elif block_type == "equation":
            expression = block_data.get("expression", "")
            if expression:
                lines.append(f"$${expression}$$")
        else:
            rich_text = block_data.get("rich_text", [])
            if not rich_text and block_type not in ["heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "to_do", "quote"]:
                continue
            
            text = rich_text_to_plain(rich_text)
            if block_type == "heading_1":
                lines.append(f"# {text}")
            elif block_type == "heading_2":
                lines.append(f"## {text}")
            elif block_type == "heading_3":
                lines.append(f"### {text}")
            elif block_type == "bulleted_list_item":
                lines.append(f"- {text}")
            elif block_type == "numbered_list_item":
                lines.append(f"1. {text}")
            elif block_type == "to_do":
                checked = "[x]" if block_data.get("checked") else "[ ]"
                lines.append(f"{checked} {text}")
            elif block_type == "quote":
                lines.append(f"> {text}")
            else:
                lines.append(text)
    
    return "\n\n".join(filter(None, lines))

async def fetch_all_blocks(client: ConnectorHttpClient, page_id: str) -> List[Dict[str, Any]]:
    all_blocks = []
    cursor = None
    has_more = True

    while has_more:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        
        response = await client.get(f"/blocks/{page_id}/children", params=params)
        if response.status_code != 200:
            logger.warning(f"Failed to fetch blocks for page {page_id}: {response.status_code}")
            break
        
        data = response.json()
        all_blocks.extend(data.get("results", []))
        cursor = data.get("next_cursor")
        has_more = data.get("has_more", False)
    
    return all_blocks

def extract_tags(properties: Dict[str, Any]) -> List[str]:
    tags = []
    for value in properties.values():
        if not isinstance(value, dict):
            continue
        prop_type = value.get("type")
        if prop_type == "multi_select" and isinstance(value.get("multi_select"), list):
            for item in value["multi_select"]:
                if isinstance(item, dict) and item.get("name"):
                    tags.append(item["name"])
        elif prop_type == "select" and isinstance(value.get("select"), dict):
            if value["select"].get("name"):
                tags.append(value["select"]["name"])
    return tags

def page_to_stub(page: Dict[str, Any]) -> ExternalDocument:
    page_id = page["id"]
    properties = page.get("properties", {})
    title = extract_title(properties)
    url = page.get("url", "")
    last_edited_time = page.get("last_edited_time", "")
    
    tags = extract_tags(properties)
    
    return ExternalDocument(
        external_id=page_id,
        title=title or "Untitled",
        content="",
        content_deferred=True,
        mime_type="text/plain",
        source_url=url,
        content_hash=f"notion:{page_id}:{last_edited_time}",
        metadata={
            "tags": tags,
            "lastModified": last_edited_time,
            "createdTime": page.get("created_time"),
            "parentType": page.get("parent", {}).get("type")
        }
    )

@registry.register
class NotionConnector(BaseConnector):
    @property
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(
            id="notion",
            name="Notion",
            description="Sync pages from a Notion workspace into your knowledge base",
            version="1.0.0",
            icon="notion",
            auth_config=OAuthAuthConfig(
                mode="oauth",
                provider="notion",
                required_scopes=[],
            ),
            config_fields=[
                ConnectorConfigField(
                    id="scope",
                    title="Sync Scope",
                    type="dropdown",
                    required=False,
                    options=[
                        Option(label="Entire workspace", id="workspace"),
                        Option(label="Specific database", id="database"),
                        Option(label="Specific page (and children)", id="page"),
                    ],
                ),
                ConnectorConfigField(
                    id="databaseSelector",
                    title="Database",
                    type="selector",
                    selector_key="notion.databases",
                    canonical_param_id="databaseId",
                    mode="basic",
                    placeholder="Select a database",
                    required=False,
                ),
                ConnectorConfigField(
                    id="databaseId",
                    title="Database ID",
                    type="short-input",
                    canonical_param_id="databaseId",
                    mode="advanced",
                    required=False,
                    placeholder="e.g. 8a3b5f6e-1234-5678-abcd-ef0123456789",
                ),
                ConnectorConfigField(
                    id="rootPageId",
                    title="Page ID",
                    type="short-input",
                    required=False,
                    placeholder="e.g. 8a3b5f6e-1234-5678-abcd-ef0123456789",
                ),
                ConnectorConfigField(
                    id="searchQuery",
                    title="Search Filter",
                    type="short-input",
                    required=False,
                    placeholder="e.g. meeting notes, project plan",
                ),
                ConnectorConfigField(
                    id="maxPages",
                    title="Max Pages",
                    type="short-input",
                    required=False,
                    placeholder="e.g. 500 (default: unlimited)",
                ),
            ],
        )

    def _get_client(self, access_token: str) -> ConnectorHttpClient:
        return ConnectorHttpClient(
            base_url=NOTION_BASE_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Notion-Version": NOTION_API_VERSION,
                "Content-Type": "application/json"
            }
        )

    async def list_documents(
        self, config: Dict[str, Any], cursor: Optional[str] = None
    ) -> ExternalDocumentList:
        access_token = config.get("accessToken")
        scope = config.get("scope", "workspace")
        database_id = config.get("databaseId", "").strip()
        root_page_id = config.get("rootPageId", "").strip()
        max_pages = int(config.get("maxPages")) if config.get("maxPages") else 0
        
        client = self._get_client(access_token)

        if scope == "database" and database_id:
            return await self._list_from_database(client, database_id, max_pages, cursor, config)
        if scope == "page" and root_page_id:
            return await self._list_from_parent_page(client, root_page_id, max_pages, cursor, config)
        
        search_query = config.get("searchQuery", "")
        return await self._list_from_workspace(client, search_query, max_pages, cursor, config)

    async def _list_from_workspace(
        self, client: ConnectorHttpClient, search_query: str, max_pages: int, cursor: Optional[str], config: Dict[str, Any]
    ) -> ExternalDocumentList:
        body = {
            "page_size": 100,
            "filter": {"value": "page", "property": "object"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"}
        }
        if search_query.strip():
            body["query"] = search_query.strip()
        if cursor:
            body["start_cursor"] = cursor
        
        response = await client.post("/search", json=body)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        pages = [r for r in results if r.get("object") == "page" and not r.get("archived")]
        documents = [page_to_stub(p) for p in pages]
        
        total_fetched = config.get("totalDocsFetched", 0) + len(documents)
        config["totalDocsFetched"] = total_fetched
        hit_limit = max_pages > 0 and total_fetched >= max_pages
        
        return ExternalDocumentList(
            documents=documents,
            next_cursor=None if hit_limit else data.get("next_cursor"),
            has_more=False if hit_limit else data.get("has_more", False)
        )

    async def _list_from_database(
        self, client: ConnectorHttpClient, database_id: str, max_pages: int, cursor: Optional[str], config: Dict[str, Any]
    ) -> ExternalDocumentList:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        
        response = await client.post(f"/databases/{database_id}/query", json=body)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        pages = [r for r in results if r.get("object") == "page" and not r.get("archived")]
        documents = [page_to_stub(p) for p in pages]
        
        total_fetched = config.get("totalDocsFetched", 0) + len(documents)
        config["totalDocsFetched"] = total_fetched
        hit_limit = max_pages > 0 and total_fetched >= max_pages
        
        return ExternalDocumentList(
            documents=documents,
            next_cursor=None if hit_limit else data.get("next_cursor"),
            has_more=False if hit_limit else data.get("has_more", False)
        )

    async def _list_from_parent_page(
        self, client: ConnectorHttpClient, root_page_id: str, max_pages: int, cursor: Optional[str], config: Dict[str, Any]
    ) -> ExternalDocumentList:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        
        response = await client.get(f"/blocks/{root_page_id}/children", params=params)
        response.raise_for_status()
        data = response.json()
        
        block_results = data.get("results", [])
        child_page_ids = [b["id"] for b in block_results if b.get("type") == "child_page"]
        
        page_ids_to_fetch = ([root_page_id] if not cursor else []) + child_page_ids
        
        documents = []
        CHILD_PAGE_CONCURRENCY = 5
        for i in range(0, len(page_ids_to_fetch), CHILD_PAGE_CONCURRENCY):
            cumulative_so_far = config.get("totalDocsFetched", 0) + len(documents)
            if max_pages > 0 and cumulative_so_far >= max_pages:
                break
            
            batch = page_ids_to_fetch[i:i+CHILD_PAGE_CONCURRENCY]
            tasks = []
            for page_id in batch:
                tasks.append(client.get(f"/pages/{page_id}"))
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for resp in responses:
                if isinstance(resp, httpx.Response) and resp.status_code == 200:
                    page = resp.json()
                    if not page.get("archived"):
                        documents.append(page_to_stub(page))
        
        total_fetched = config.get("totalDocsFetched", 0) + len(documents)
        config["totalDocsFetched"] = total_fetched
        hit_limit = max_pages > 0 and total_fetched >= max_pages
        
        return ExternalDocumentList(
            documents=documents,
            next_cursor=None if hit_limit else data.get("next_cursor"),
            has_more=False if hit_limit else data.get("has_more", False)
        )

    async def get_document(
        self, external_id: str, config: Dict[str, Any]
    ) -> ExternalDocument:
        access_token = config.get("accessToken")
        client = self._get_client(access_token)
        
        response = await client.get(f"/pages/{external_id}")
        if response.status_code == 404:
            raise Exception(f"Page {external_id} not found")
        response.raise_for_status()
        
        page = response.json()
        if page.get("archived"):
            raise Exception(f"Page {external_id} is archived")
        
        blocks = await fetch_all_blocks(client, external_id)
        block_content = blocks_to_plain_text(blocks)
        stub = page_to_stub(page)
        
        content = block_content.strip() or stub.title
        stub.content = content
        stub.content_deferred = False
        return stub

    async def validate_config(self, config: Dict[str, Any]) -> None:
        access_token = config.get("accessToken")
        scope = config.get("scope", "workspace")
        database_id = config.get("databaseId", "").strip()
        root_page_id = config.get("rootPageId", "").strip()
        
        max_pages = config.get("maxPages")
        if max_pages:
            try:
                if int(max_pages) <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("Max pages must be a positive number")

        if scope == "database" and not database_id:
            raise ValueError("Database ID is required when scope is 'Specific database'")
        if scope == "page" and not root_page_id:
            raise ValueError("Page ID is required when scope is 'Specific page'")

        client = self._get_client(access_token)
        
        if scope == "database" and database_id:
            response = await client.get(f"/databases/{database_id}")
            if response.status_code != 200:
                raise ValueError(f"Cannot access database: {response.status_code}")
        elif scope == "page" and root_page_id:
            response = await client.get(f"/pages/{root_page_id}")
            if response.status_code != 200:
                raise ValueError(f"Cannot access page: {response.status_code}")
        else:
            response = await client.post("/search", json={"page_size": 1})
            if response.status_code != 200:
                raise Exception(f"Cannot access Notion workspace: {response.status_code} - {response.text}")
