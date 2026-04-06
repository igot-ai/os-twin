import httpx
import logging
import asyncio
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
from .utils import compute_content_hash, html_to_plain_text, parse_tag_date
from .client import ConnectorHttpClient
from .registry import registry

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
DEFAULT_MAX_MESSAGES = 1000
MESSAGES_PER_PAGE = 50

def format_messages(messages: List[Dict[str, Any]]) -> str:
    lines = []
    # Process in reverse so oldest messages come first
    chronological = messages[::-1]
    
    for msg in chronological:
        body = msg.get("body", {})
        content = body.get("content", "")
        if body.get("contentType") == "html":
            content = html_to_plain_text(content)
        
        if not content.strip():
            continue
            
        timestamp = msg.get("createdDateTime")
        from_info = msg.get("from", {})
        user_name = (
            from_info.get("user", {}).get("displayName") or 
            from_info.get("application", {}).get("displayName") or 
            "unknown"
        )
        
        lines.append(f"[{timestamp}] {user_name}: {content}")
        
    return "\n".join(lines)

async def fetch_channel_messages(
    client: ConnectorHttpClient,
    team_id: str,
    channel_id: str,
    max_messages: int
) -> Dict[str, Any]:
    all_messages = []
    next_link = None
    last_activity_ts = None
    
    initial_path = f"/teams/{quote(team_id)}/channels/{quote(channel_id)}/messages?$top={min(MESSAGES_PER_PAGE, max_messages)}"
    current_url = initial_path
    
    while len(all_messages) < max_messages:
        response = await client.get(current_url)
        response.raise_for_status()
        data = response.json()
        
        messages = data.get("value", [])
        if not messages:
            break
            
        user_messages = [
            m for m in messages 
            if m.get("messageType") == "message" and not m.get("deletedDateTime")
        ]
        
        if not last_activity_ts and user_messages:
            last_activity_ts = user_messages[0].get("createdDateTime")
            
        all_messages.extend(user_messages)
        
        next_link = data.get("@odata.nextLink")
        if not next_link:
            break
        current_url = next_link
        
    return {
        "messages": all_messages[:max_messages],
        "lastActivityTs": last_activity_ts
    }

async def resolve_channel(
    client: ConnectorHttpClient,
    team_id: str,
    channel_input: str
) -> Optional[Dict[str, Any]]:
    trimmed = channel_input.strip()
    next_link = None
    initial_path = f"/teams/{quote(team_id)}/channels"
    current_url = initial_path
    
    while True:
        response = await client.get(current_url)
        response.raise_for_status()
        data = response.json()
        channels = data.get("value", [])
        
        match = next(
            (ch for ch in channels if ch["id"] == trimmed or ch["displayName"].lower() == trimmed.lower()),
            None
        )
        if match:
            return match
            
        next_link = data.get("@odata.nextLink")
        if not next_link:
            break
        current_url = next_link
        
    return None

@registry.register
class MicrosoftTeamsConnector(BaseConnector):
    @property
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(
            id="microsoft_teams",
            name="Microsoft Teams",
            description="Sync channel messages from Microsoft Teams into your knowledge base",
            version="1.0.0",
            icon="microsoft_teams",
            auth_config=OAuthAuthConfig(
                mode="oauth",
                provider="microsoft-teams",
                required_scopes=["ChannelMessage.Read.All", "Channel.ReadBasic.All"],
            ),
            config_fields=[
                ConnectorConfigField(
                    id="teamSelector",
                    title="Team",
                    type="selector",
                    selector_key="microsoft.teams",
                    canonical_param_id="teamId",
                    mode="basic",
                    placeholder="Select a team",
                    required=True,
                ),
                ConnectorConfigField(
                    id="teamId",
                    title="Team ID",
                    type="short-input",
                    canonical_param_id="teamId",
                    mode="advanced",
                    placeholder="e.g. fbe2bf47-16c8-47cf-b4a5-4b9b187c508b",
                    required=True,
                    description="The ID of the Microsoft Teams team",
                ),
                ConnectorConfigField(
                    id="channelSelector",
                    title="Channel",
                    type="selector",
                    selector_key="microsoft.channels",
                    canonical_param_id="channel",
                    mode="basic",
                    depends_on=["teamSelector"],
                    placeholder="Select a channel",
                    required=True,
                ),
                ConnectorConfigField(
                    id="channel",
                    title="Channel",
                    type="short-input",
                    canonical_param_id="channel",
                    mode="advanced",
                    placeholder="e.g. General or 19:abc123@thread.tacv2",
                    required=True,
                    description="Channel name or ID to sync messages from",
                ),
                ConnectorConfigField(
                    id="maxMessages",
                    title="Max Messages",
                    type="short-input",
                    required=False,
                    placeholder=f"e.g. 500 (default: {DEFAULT_MAX_MESSAGES})",
                ),
            ],
        )

    def _get_client(self, access_token: str) -> ConnectorHttpClient:
        return ConnectorHttpClient(
            base_url=GRAPH_API_BASE,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
        )

    async def list_documents(
        self, config: Dict[str, Any], cursor: Optional[str] = None
    ) -> ExternalDocumentList:
        access_token = config.get("accessToken")
        team_id = config.get("teamId")
        channel_input = config.get("channel")
        max_messages = int(config.get("maxMessages")) if config.get("maxMessages") else DEFAULT_MAX_MESSAGES
        
        if not team_id: raise ValueError("Team ID is required")
        if not channel_input: raise ValueError("Channel is required")
        
        client = self._get_client(access_token)
        
        channel = await resolve_channel(client, team_id, channel_input)
        if not channel:
            raise Exception(f"Channel not found: {channel_input}")
            
        result = await fetch_channel_messages(client, team_id, channel["id"], max_messages)
        messages = result["messages"]
        last_activity_ts = result["lastActivityTs"]
        
        content = format_messages(messages)
        if not content.strip():
            return ExternalDocumentList(documents=[], next_cursor=None, has_more=False)
            
        content_hash = compute_content_hash(content)
        source_url = f"https://teams.microsoft.com/l/channel/{quote(channel['id'])}/{quote(channel['displayName'])}?groupId={quote(team_id)}"
        
        doc = ExternalDocument(
            external_id=channel["id"],
            title=channel["displayName"],
            content=content,
            mime_type="text/plain",
            source_url=source_url,
            content_hash=content_hash,
            metadata={
                "channelName": channel["displayName"],
                "messageCount": len(messages),
                "lastActivity": last_activity_ts,
                "description": channel.get("description")
            }
        )
        
        return ExternalDocumentList(documents=[doc], next_cursor=None, has_more=False)

    async def get_document(
        self, external_id: str, config: Dict[str, Any]
    ) -> ExternalDocument:
        access_token = config.get("accessToken")
        team_id = config.get("teamId")
        max_messages = int(config.get("maxMessages")) if config.get("maxMessages") else DEFAULT_MAX_MESSAGES
        
        if not team_id: raise ValueError("Team ID is required")
        
        client = self._get_client(access_token)
        
        # Fetch channel info
        response = await client.get(f"/teams/{quote(team_id)}/channels/{quote(external_id)}")
        response.raise_for_status()
        channel = response.json()
        
        result = await fetch_channel_messages(client, team_id, external_id, max_messages)
        messages = result["messages"]
        last_activity_ts = result["lastActivityTs"]
        
        content = format_messages(messages)
        if not content.strip():
            raise Exception(f"No content found in channel {external_id}")
            
        content_hash = compute_content_hash(content)
        source_url = f"https://teams.microsoft.com/l/channel/{quote(channel['id'])}/{quote(channel['displayName'])}?groupId={quote(team_id)}"
        
        return ExternalDocument(
            external_id=channel["id"],
            title=channel["displayName"],
            content=content,
            mime_type="text/plain",
            source_url=source_url,
            content_hash=content_hash,
            metadata={
                "channelName": channel["displayName"],
                "messageCount": len(messages),
                "lastActivity": last_activity_ts,
                "description": channel.get("description")
            }
        )

    async def validate_config(self, config: Dict[str, Any]) -> None:
        access_token = config.get("accessToken")
        team_id = config.get("teamId")
        channel_input = config.get("channel")
        
        if not team_id: raise ValueError("Team ID is required")
        if not channel_input: raise ValueError("Channel is required")
        
        max_messages = config.get("maxMessages")
        if max_messages:
            try:
                if int(max_messages) <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("Max messages must be a positive number")

        client = self._get_client(access_token)
        channel = await resolve_channel(client, team_id, channel_input)
        if not channel:
            raise ValueError(f"Channel not found: {channel_input}")
            
        # Verify we can read messages
        response = await client.get(f"/teams/{quote(team_id)}/channels/{quote(channel['id'])}/messages?$top=1")
        if response.status_code != 200:
            raise Exception(f"Failed to access Microsoft Teams: {response.status_code}")
