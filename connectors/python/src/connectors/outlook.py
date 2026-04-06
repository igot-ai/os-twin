import httpx
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Set
from urllib.parse import urlencode
from .base import BaseConnector
from .models import (
    ConnectorConfig,
    ExternalDocument,
    ExternalDocumentList,
    OAuthAuthConfig,
    ConnectorConfigField,
    Option,
)
from .utils import compute_content_hash, html_to_plain_text, parse_tag_date
from .client import ConnectorHttpClient
from .registry import registry

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0/me"
DEFAULT_MAX_CONVERSATIONS = 500
MESSAGES_PER_PAGE = 50
MAX_TOTAL_MESSAGES = 5000

MESSAGE_FIELDS = [
    "id", "conversationId", "subject", "from", "toRecipients",
    "receivedDateTime", "sentDateTime", "body", "categories",
    "importance", "inferenceClassification", "hasAttachments",
    "webLink", "isDraft", "parentFolderId",
]

WELL_KNOWN_FOLDERS = {
    "inbox": "inbox",
    "sentitems": "sentitems",
    "drafts": "drafts",
    "deleteditems": "deleteditems",
    "archive": "archive",
    "junkemail": "junkemail",
}

def get_date_range_iso(date_range: str) -> Optional[str]:
    now = datetime.utcnow()
    days_back = None
    if date_range == "7d": days_back = 7
    elif date_range == "30d": days_back = 30
    elif date_range == "90d": days_back = 90
    elif date_range == "6m": days_back = 180
    elif date_range == "1y": days_back = 365
    else: return None
    
    date = now - timedelta(days=days_back)
    return date.isoformat() + "Z"

def build_initial_url(source_config: Dict[str, Any]) -> str:
    folder = source_config.get("folder") or "inbox"
    base_path = (
        f"{GRAPH_API_BASE}/messages" if folder == "all"
        else f"{GRAPH_API_BASE}/mailFolders/{WELL_KNOWN_FOLDERS.get(folder, folder)}/messages"
    )
    
    params = {
        "$top": MESSAGES_PER_PAGE,
        "$select": ",".join(MESSAGE_FIELDS),
    }
    
    filter_parts = []
    date_range = source_config.get("dateRange") or "all"
    date_iso = get_date_range_iso(date_range)
    if date_iso:
        filter_parts.append(f"receivedDateTime ge {date_iso}")
    
    search_query = source_config.get("query")
    has_search = bool(search_query and search_query.strip())
    
    if not has_search:
        filter_parts.append("isDraft eq false")
    
    focused_only = source_config.get("focusedOnly") != "false"
    if focused_only and not has_search:
        filter_parts.append("inferenceClassification eq 'focused'")
    
    if filter_parts:
        params["$filter"] = " and ".join(filter_parts)
    
    if has_search:
        params["$search"] = f'"{search_query.strip()}"'
    
    return f"{base_path}?{urlencode(params)}"

def format_recipient(recipient: Optional[Dict[str, Any]]) -> str:
    if not recipient or not recipient.get("emailAddress"):
        return "Unknown"
    addr = recipient["emailAddress"]
    name = addr.get("name")
    address = addr.get("address")
    if name and address:
        return f"{name} <{address}>"
    return name or address or "Unknown"

def extract_body_text(body: Optional[Dict[str, Any]]) -> str:
    if not body or not body.get("content"):
        return ""
    if body.get("contentType", "").lower() == "text":
        return body["content"]
    return html_to_plain_text(body["content"])

def format_conversation(
    conversation_id: str,
    messages: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    if not messages:
        return None
    
    sorted_msgs = sorted(
        messages,
        key=lambda m: m.get("receivedDateTime") or ""
    )
    
    first = sorted_msgs[0]
    last = sorted_msgs[-1]
    subject = first.get("subject") or "No Subject"
    from_str = format_recipient(first.get("from"))
    to_str = ", ".join(format_recipient(r) for r in first.get("toRecipients", []))
    
    lines = [
        f"Subject: {subject}",
        f"From: {from_str}",
        f"To: {to_str}" if to_str else "",
        f"Messages: {len(sorted_msgs)}",
        ""
    ]
    
    for msg in sorted_msgs:
        msg_from = format_recipient(msg.get("from"))
        msg_date = msg.get("receivedDateTime") or ""
        body = extract_body_text(msg.get("body"))
        lines.append(f"--- {msg_from} ({msg_date}) ---")
        lines.append(body.strip())
        lines.append("")
    
    content = "\n".join(lines).strip()
    if not content:
        return None
    
    categories = set()
    for msg in sorted_msgs:
        for cat in msg.get("categories", []):
            categories.add(cat)
            
    return {
        "content": content,
        "subject": subject,
        "metadata": {
            "from": from_str,
            "to": to_str,
            "subject": subject,
            "conversationId": conversation_id,
            "messageCount": len(sorted_msgs),
            "categories": list(categories),
            "importance": first.get("importance"),
            "firstMessageDate": first.get("receivedDateTime"),
            "lastMessageDate": last.get("receivedDateTime"),
            "hasAttachments": any(m.get("hasAttachments") for m in sorted_msgs),
        }
    }

@registry.register
class OutlookConnector(BaseConnector):
    @property
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(
            id="outlook",
            name="Outlook",
            description="Sync email conversations from Outlook into your knowledge base",
            version="1.0.0",
            icon="outlook",
            auth_config=OAuthAuthConfig(
                mode="oauth",
                provider="outlook",
                required_scopes=["Mail.Read"],
            ),
            config_fields=[
                ConnectorConfigField(
                    id="folderSelector",
                    title="Folder",
                    type="selector",
                    selector_key="outlook.folders",
                    canonical_param_id="folder",
                    mode="basic",
                    placeholder="Select a folder",
                    required=False,
                ),
                ConnectorConfigField(
                    id="folder",
                    title="Folder",
                    type="dropdown",
                    canonical_param_id="folder",
                    mode="advanced",
                    required=False,
                    options=[
                        Option(label="Inbox", id="inbox"),
                        Option(label="All Mail", id="all"),
                        Option(label="Sent Items", id="sentitems"),
                        Option(label="Archive", id="archive"),
                    ],
                ),
                ConnectorConfigField(
                    id="dateRange",
                    title="Date Range",
                    type="dropdown",
                    required=False,
                    options=[
                        Option(label="Last 7 days", id="7d"),
                        Option(label="Last 30 days", id="30d"),
                        Option(label="Last 90 days", id="90d"),
                        Option(label="Last 6 months", id="6m"),
                        Option(label="Last year", id="1y"),
                        Option(label="All time", id="all"),
                    ],
                ),
                ConnectorConfigField(
                    id="focusedOnly",
                    title="Focused Inbox Only",
                    type="dropdown",
                    required=False,
                    options=[
                        Option(label="Yes (recommended)", id="true"),
                        Option(label="No", id="false"),
                    ],
                ),
                ConnectorConfigField(
                    id="query",
                    title="Search Filter",
                    type="short-input",
                    placeholder="e.g. from:boss@company.com subject:report hasAttachment:true",
                    required=False,
                    description="Search filter using Outlook KQL syntax.",
                ),
                ConnectorConfigField(
                    id="maxConversations",
                    title="Max Conversations",
                    type="short-input",
                    required=False,
                    placeholder=f"e.g. 200 (default: {DEFAULT_MAX_CONVERSATIONS})",
                ),
            ],
        )

    def _get_client(self, access_token: str) -> ConnectorHttpClient:
        return ConnectorHttpClient(
            base_url="",  # Relative URLs used in builds
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Prefer": 'outlook.body-content-type="text"'
            }
        )

    async def list_documents(
        self, config: Dict[str, Any], cursor: Optional[str] = None
    ) -> ExternalDocumentList:
        access_token = config.get("accessToken")
        max_conversations = int(config.get("maxConversations")) if config.get("maxConversations") else DEFAULT_MAX_CONVERSATIONS
        
        if "_conversations" not in config:
            config["_conversations"] = {}
            config["_totalMessagesFetched"] = 0
            config["_fetchComplete"] = False
            
        conversations = config["_conversations"]
        total_fetched = config["_totalMessagesFetched"]
        
        client = self._get_client(access_token)
        
        if not config.get("_fetchComplete"):
            url = cursor or build_initial_url(config)
            
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            messages = data.get("value", [])
            focused_only = config.get("focusedOnly") != "false"
            search_query = config.get("query")
            has_search = bool(search_query and search_query.strip())
            
            for msg in messages:
                if has_search and msg.get("isDraft"): continue
                if focused_only and has_search and msg.get("inferenceClassification") != "focused": continue
                
                conv_id = msg.get("conversationId") or msg.get("id")
                if conv_id not in conversations:
                    conversations[conv_id] = []
                conversations[conv_id].append(msg)
                
            new_total = total_fetched + len(messages)
            config["_totalMessagesFetched"] = new_total
            
            next_link = data.get("@odata.nextLink")
            if next_link and new_total < MAX_TOTAL_MESSAGES:
                return ExternalDocumentList(documents=[], next_cursor=next_link, has_more=True)
            
            config["_fetchComplete"] = True
            
        # Grouping
        conversation_entries = list(conversations.items())
        
        def get_max_date(msgs):
            return max((m.get("receivedDateTime") or "" for m in msgs), default="")
            
        conversation_entries.sort(key=lambda x: get_max_date(x[1]), reverse=True)
        limited = conversation_entries[:max_conversations]
        
        documents = []
        for conv_id, msgs in limited:
            result = format_conversation(conv_id, msgs)
            if not result: continue
            
            content_hash = compute_content_hash(result["content"])
            first_with_link = next((m for m in msgs if m.get("webLink")), None)
            source_url = first_with_link.get("webLink") if first_with_link else "https://outlook.office.com/mail/inbox"
            
            documents.append(ExternalDocument(
                external_id=conv_id,
                title=result["subject"],
                content=result["content"],
                mime_type="text/plain",
                source_url=source_url,
                content_hash=content_hash,
                metadata=result["metadata"]
            ))
            
        return ExternalDocumentList(documents=documents, next_cursor=None, has_more=False)

    async def get_document(
        self, external_id: str, config: Dict[str, Any]
    ) -> ExternalDocument:
        access_token = config.get("accessToken")
        client = self._get_client(access_token)
        
        safe_id = external_id.replace("'", "''")
        params = {
            "$filter": f"conversationId eq '{safe_id}'",
            "$select": ",".join(MESSAGE_FIELDS),
            "$top": 50,
        }
        
        url = f"{GRAPH_API_BASE}/messages?{urlencode(params)}"
        response = await client.get(url)
        if response.status_code == 404:
            raise Exception(f"Outlook conversation {external_id} not found")
        response.raise_for_status()
        
        data = response.json()
        messages = data.get("value", [])
        if not messages:
            raise Exception(f"Outlook conversation {external_id} not found")
            
        result = format_conversation(external_id, messages)
        if not result:
            raise Exception(f"Failed to format Outlook conversation {external_id}")
            
        content_hash = compute_content_hash(result["content"])
        first_with_link = next((m for m in messages if m.get("webLink")), None)
        
        return ExternalDocument(
            external_id=external_id,
            title=result["subject"],
            content=result["content"],
            mime_type="text/plain",
            source_url=first_with_link.get("webLink") if first_with_link else "https://outlook.office.com/mail/inbox",
            content_hash=content_hash,
            metadata=result["metadata"]
        )

    async def validate_config(self, config: Dict[str, Any]) -> None:
        access_token = config.get("accessToken")
        max_conv = config.get("maxConversations")
        if max_conv:
            try:
                if int(max_conv) <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("Max conversations must be a positive number")

        client = self._get_client(access_token)
        folder = config.get("folder") or "inbox"
        test_url = (
            f"{GRAPH_API_BASE}/messages?$top=1&$select=id" if folder == "all"
            else f"{GRAPH_API_BASE}/mailFolders/{WELL_KNOWN_FOLDERS.get(folder, folder)}/messages?$top=1&$select=id"
        )
        
        response = await client.get(test_url)
        if response.status_code != 200:
            if response.status_code == 404:
                raise ValueError(f"Folder '{folder}' not found")
            raise Exception(f"Failed to access Outlook: {response.status_code}")
            
        search_query = config.get("query")
        if search_query and search_query.strip():
            search_url = f"{GRAPH_API_BASE}/messages?$search=\"{search_query.strip()}\"&$top=1&$select=id"
            search_response = await client.get(search_url)
            if search_response.status_code != 200:
                raise ValueError("Invalid search query. Check Outlook search syntax.")
