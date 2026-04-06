import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from .base import BaseConnector
from .models import (
    ConnectorConfig,
    ExternalDocument,
    ExternalDocumentList,
    ApiKeyAuthConfig,
    ConnectorConfigField,
    Option,
)
from .utils import html_to_plain_text, compute_content_hash
from .registry import registry

INTERCOM_API_BASE = "https://api.intercom.io"
DEFAULT_MAX_ITEMS = 500
ARTICLES_PER_PAGE = 50
CONVERSATIONS_PER_PAGE = 50


@registry.register
class IntercomConnector(BaseConnector):
    @property
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(
            id="intercom",
            name="Intercom",
            description=(
                "Sync Help Center articles and conversations from Intercom "
                "into your knowledge base"
            ),
            version="1.0.0",
            icon="intercom",
            auth_config=ApiKeyAuthConfig(
                mode="apiKey",
                label="Access Token",
                placeholder="Enter your Intercom access token",
            ),
            config_fields=[
                ConnectorConfigField(
                    id="contentType",
                    title="Content Type",
                    type="dropdown",
                    required=True,
                    description="Choose what to sync from Intercom",
                    options=[
                        Option(label="Articles Only", id="articles"),
                        Option(label="Conversations Only", id="conversations"),
                        Option(label="Articles & Conversations", id="both"),
                    ],
                ),
                ConnectorConfigField(
                    id="articleState",
                    title="Article State",
                    type="dropdown",
                    required=False,
                    description="Filter articles by state (default: published)",
                    options=[
                        Option(label="Published", id="published"),
                        Option(label="Draft", id="draft"),
                        Option(label="All", id="all"),
                    ],
                ),
                ConnectorConfigField(
                    id="conversationState",
                    title="Conversation State",
                    type="dropdown",
                    required=False,
                    description="Filter conversations by state (default: all)",
                    options=[
                        Option(label="Open", id="open"),
                        Option(label="Closed", id="closed"),
                        Option(label="All", id="all"),
                    ],
                ),
                ConnectorConfigField(
                    id="maxItems",
                    title="Max Items",
                    type="short-input",
                    required=False,
                    placeholder=f"e.g. 200 (default: {DEFAULT_MAX_ITEMS})",
                    description=(
                        "Maximum number of articles or conversations to sync"
                    ),
                ),
            ],
        )

    async def _api_get(
        self, path: str, access_token: str, params: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Intercom-Version": "2.11",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{INTERCOM_API_BASE}{path}", headers=headers, params=params
            )
            if response.status_code != 200:
                raise Exception(
                    f"Intercom API HTTP error {response.status_code}: {response.text}"
                )
            return response.json()

    async def list_documents(
        self, config: Dict[str, Any], cursor: Optional[str] = None
    ) -> ExternalDocumentList:
        access_token = config.get("apiKey")
        if not access_token:
            raise ValueError("API Key (Access Token) is required")

        content_type = config.get("contentType", "articles")
        article_state = config.get("articleState", "published")
        conversation_state = config.get("conversationState", "all")
        max_items = (
            int(config.get("maxItems")) if config.get("maxItems") else DEFAULT_MAX_ITEMS
        )

        documents = []

        if content_type in ["articles", "both"]:
            articles = await self._fetch_articles(
                access_token, max_items, article_state
            )
            for article in articles:
                content = self._format_article(article)
                if not content.strip():
                    continue

                documents.append(
                    ExternalDocument(
                        externalId=f"article-{article['id']}",
                        title=article.get("title") or f"Article {article['id']}",
                        content=content,
                        mimeType="text/plain",
                        sourceUrl=(
                            f"https://app.intercom.com/a/apps/_/articles/"
                            f"articles/{article['id']}/show"
                        ),
                        contentHash=compute_content_hash(content),
                        metadata={
                            "type": "article",
                            "state": article.get("state"),
                            "authorId": str(article.get("author_id")),
                            "updatedAt": datetime.fromtimestamp(
                                article["updated_at"]
                            ).isoformat(),
                            "createdAt": datetime.fromtimestamp(
                                article["created_at"]
                            ).isoformat(),
                        },
                    )
                )

        if content_type in ["conversations", "both"]:
            conversations = await self._fetch_conversations(
                access_token, max_items, conversation_state
            )
            for conv in conversations:
                detail = await self._api_get(
                    f"/conversations/{conv['id']}", access_token
                )
                content = self._format_conversation(detail)
                if not content.strip():
                    continue

                tags = [t["name"] for t in conv.get("tags", {}).get("tags", [])]

                documents.append(
                    ExternalDocument(
                        externalId=f"conversation-{conv['id']}",
                        title=conv.get("title") or f"Conversation #{conv['id']}",
                        content=content,
                        mimeType="text/plain",
                        sourceUrl=(
                            f"https://app.intercom.com/a/apps/_/inbox/inbox/"
                            f"all/conversations/{conv['id']}"
                        ),
                        contentHash=compute_content_hash(content),
                        metadata={
                            "type": "conversation",
                            "state": conv.get("state"),
                            "tags": ", ".join(tags),
                            "updatedAt": datetime.fromtimestamp(
                                conv["updated_at"]
                            ).isoformat(),
                            "createdAt": datetime.fromtimestamp(
                                conv["created_at"]
                            ).isoformat(),
                            "messageCount": (
                                detail.get("conversation_parts", {}).get(
                                    "total_count", 0
                                )
                            )
                            + 1,
                        },
                    )
                )

        return ExternalDocumentList(documents=documents, hasMore=False)

    async def get_document(
        self, external_id: str, config: Dict[str, Any]
    ) -> ExternalDocument:
        access_token = config.get("apiKey")
        if not access_token:
            raise ValueError("API Key (Access Token) is required")

        if external_id.startswith("article-"):
            article_id = external_id.replace("article-", "")
            article = await self._api_get(f"/articles/{article_id}", access_token)
            content = self._format_article(article)
            return ExternalDocument(
                externalId=external_id,
                title=article.get("title") or f"Article {article['id']}",
                content=content,
                mimeType="text/plain",
                sourceUrl=(
                    f"https://app.intercom.com/a/apps/_/articles/"
                    f"articles/{article['id']}/show"
                ),
                contentHash=compute_content_hash(content),
                metadata={
                    "type": "article",
                    "state": article.get("state"),
                    "authorId": str(article.get("author_id")),
                    "updatedAt": datetime.fromtimestamp(
                        article["updated_at"]
                    ).isoformat(),
                    "createdAt": datetime.fromtimestamp(
                        article["created_at"]
                    ).isoformat(),
                },
            )
        elif external_id.startswith("conversation-"):
            conversation_id = external_id.replace("conversation-", "")
            detail = await self._api_get(
                f"/conversations/{conversation_id}", access_token
            )
            content = self._format_conversation(detail)
            tags = [t["name"] for t in detail.get("tags", {}).get("tags", [])]
            return ExternalDocument(
                externalId=external_id,
                title=detail.get("title") or f"Conversation #{detail['id']}",
                content=content,
                mimeType="text/plain",
                sourceUrl=(
                    f"https://app.intercom.com/a/apps/_/inbox/inbox/"
                    f"all/conversations/{detail['id']}"
                ),
                contentHash=compute_content_hash(content),
                metadata={
                    "type": "conversation",
                    "state": detail.get("state"),
                    "tags": ", ".join(tags),
                    "updatedAt": datetime.fromtimestamp(
                        detail["updated_at"]
                    ).isoformat(),
                    "createdAt": datetime.fromtimestamp(
                        detail["created_at"]
                    ).isoformat(),
                    "messageCount": (
                        detail.get("conversation_parts", {}).get("total_count", 0)
                    )
                    + 1,
                },
            )
        else:
            raise ValueError(f"Unknown external ID format: {external_id}")

    async def validate_config(self, config: Dict[str, Any]) -> None:
        access_token = config.get("apiKey")
        if not access_token:
            raise ValueError("API Key (Access Token) is required")

        content_type = config.get("contentType")
        if not content_type:
            raise ValueError("Content type is required")

        max_items = config.get("maxItems")
        if max_items:
            try:
                val = int(max_items)
                if val <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("Max items must be a positive number")

        # Verify API access
        if content_type in ["articles", "both"]:
            await self._api_get(
                "/articles", access_token, params={"page": "1", "per_page": "1"}
            )

        if content_type in ["conversations", "both"]:
            await self._api_get(
                "/conversations", access_token, params={"per_page": "1"}
            )

    async def _fetch_articles(
        self, access_token: str, max_items: int, state_filter: str
    ) -> List[Dict[str, Any]]:
        all_articles = []
        page = 1
        while len(all_articles) < max_items:
            data = await self._api_get(
                "/articles",
                access_token,
                params={"page": str(page), "per_page": str(ARTICLES_PER_PAGE)},
            )
            articles = data.get("data", [])
            if not articles:
                break

            for article in articles:
                if state_filter != "all" and article.get("state") != state_filter:
                    continue
                all_articles.append(article)
                if len(all_articles) >= max_items:
                    break

            total_pages = data.get("pages", {}).get("total_pages")
            if not total_pages or page >= total_pages:
                break
            page += 1
        return all_articles

    async def _fetch_conversations(
        self, access_token: str, max_items: int, state_filter: str
    ) -> List[Dict[str, Any]]:
        all_conversations = []
        starting_after = None
        while len(all_conversations) < max_items:
            params = {"per_page": str(min(CONVERSATIONS_PER_PAGE, 150))}
            if starting_after:
                params["starting_after"] = starting_after

            data = await self._api_get("/conversations", access_token, params=params)
            conversations = data.get("conversations", [])
            if not conversations:
                break

            for conv in conversations:
                if state_filter != "all" and conv.get("state") != state_filter:
                    continue
                all_conversations.append(conv)
                if len(all_conversations) >= max_items:
                    break

            next_cursor = (
                data.get("pages", {}).get("next", {}).get("starting_after")
            )
            if not next_cursor:
                break
            starting_after = next_cursor
        return all_conversations

    def _format_article(self, article: Dict[str, Any]) -> str:
        parts = []
        if article.get("title"):
            parts.append(article["title"])
        if article.get("description"):
            parts.append(article["description"])
        if article.get("body"):
            parts.append(html_to_plain_text(article["body"]))
        return "\n\n".join(parts)

    def _format_conversation(self, conversation: Dict[str, Any]) -> str:
        lines = []
        if conversation.get("title"):
            lines.append(f"Subject: {conversation['title']}")

        source = conversation.get("source", {})
        if source.get("body"):
            author = source.get("author", {})
            author_name = author.get("name") or author.get("type") or "unknown"
            ts = datetime.fromtimestamp(conversation["created_at"]).isoformat()
            lines.append(
                f"[{ts}] {author_name}: {html_to_plain_text(source['body'])}"
            )

        parts = conversation.get("conversation_parts", {}).get("conversation_parts", [])
        for part in parts:
            if not part.get("body"):
                continue
            author = part.get("author", {})
            author_name = author.get("name") or author.get("type") or "unknown"
            ts = datetime.fromtimestamp(part["created_at"]).isoformat()
            lines.append(f"[{ts}] {author_name}: {html_to_plain_text(part['body'])}")

        return "\n".join(lines)
