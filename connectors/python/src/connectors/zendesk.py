import httpx
import base64
from typing import Dict, Any, Optional, List
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

ARTICLES_PER_PAGE = 30
TICKETS_PER_PAGE = 100
DEFAULT_MAX_TICKETS = 500


@registry.register
class ZendeskConnector(BaseConnector):
    @property
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(
            id="zendesk",
            name="Zendesk",
            description=(
                "Sync Help Center articles and support tickets from Zendesk "
                "into your knowledge base"
            ),
            version="1.0.0",
            icon="zendesk",
            auth_config=ApiKeyAuthConfig(
                mode="apiKey",
                label="API Token",
                placeholder="Enter your Zendesk API token",
            ),
            config_fields=[
                ConnectorConfigField(
                    id="subdomain",
                    title="Subdomain",
                    type="short-input",
                    placeholder="yourcompany (from yourcompany.zendesk.com)",
                    required=True,
                    description="Your Zendesk subdomain",
                ),
                ConnectorConfigField(
                    id="email",
                    title="Email",
                    type="short-input",
                    placeholder="agent@yourcompany.com",
                    required=True,
                    description=(
                        "Email address of the Zendesk user "
                        "for API authentication"
                    ),
                ),
                ConnectorConfigField(
                    id="contentType",
                    title="Content Type",
                    type="dropdown",
                    required=True,
                    description="What content to sync from Zendesk",
                    options=[
                        Option(label="Articles & Tickets", id="both"),
                        Option(label="Help Center Articles Only", id="articles"),
                        Option(label="Support Tickets Only", id="tickets"),
                    ],
                ),
                ConnectorConfigField(
                    id="ticketStatus",
                    title="Ticket Status Filter",
                    type="dropdown",
                    required=False,
                    description=(
                        "Filter tickets by status "
                        "(applies only when syncing tickets)"
                    ),
                    options=[
                        Option(label="All Statuses", id="all"),
                        Option(label="Open", id="open"),
                        Option(label="Pending", id="pending"),
                        Option(label="Solved", id="solved"),
                        Option(label="Closed", id="closed"),
                    ],
                ),
                ConnectorConfigField(
                    id="locale",
                    title="Article Locale",
                    type="short-input",
                    required=False,
                    placeholder="e.g. en-us (default: all locales)",
                    description="Locale for Help Center articles",
                ),
                ConnectorConfigField(
                    id="maxTickets",
                    title="Max Tickets",
                    type="short-input",
                    required=False,
                    placeholder=f"e.g. 200 (default: {DEFAULT_MAX_TICKETS})",
                    description="Maximum number of tickets to sync",
                ),
            ],
        )

    def _build_base_url(self, subdomain: str) -> str:
        return f"https://{subdomain}.zendesk.com"

    async def _api_get(
        self, url: str, access_token: str, email: str
    ) -> Dict[str, Any]:
        auth_str = f"{email}/token:{access_token}"
        auth_bytes = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {auth_bytes}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise Exception(
                    f"Zendesk API HTTP error {response.status_code}: {response.text}"
                )
            return response.json()

    async def list_documents(
        self, config: Dict[str, Any], cursor: Optional[str] = None
    ) -> ExternalDocumentList:
        subdomain = config.get("subdomain", "").strip()
        if not subdomain:
            raise ValueError("Subdomain is required")

        email = config.get("email", "").strip()
        if not email:
            raise ValueError("Email is required")

        access_token = config.get("apiKey")
        if not access_token:
            raise ValueError("API Token is required")

        content_type = config.get("contentType", "both")
        ticket_status = config.get("ticketStatus", "all")
        locale = config.get("locale", "").strip()
        max_tickets = (
            int(config.get("maxTickets"))
            if config.get("maxTickets")
            else DEFAULT_MAX_TICKETS
        )

        documents = []
        base_url = self._build_base_url(subdomain)

        if content_type in ["articles", "both"]:
            articles = await self._fetch_articles(base_url, access_token, email, locale)
            for article in articles:
                if not article.get("body", "").strip():
                    continue
                documents.append(await self._article_to_document(article, subdomain))

        if content_type in ["tickets", "both"]:
            tickets = await self._fetch_tickets(
                base_url, access_token, email, ticket_status, max_tickets
            )
            for ticket in tickets:
                comments = await self._fetch_ticket_comments(
                    base_url, access_token, email, ticket["id"]
                )
                documents.append(
                    self._ticket_to_document(ticket, comments, subdomain)
                )

        return ExternalDocumentList(documents=documents, hasMore=False)

    async def get_document(
        self, external_id: str, config: Dict[str, Any]
    ) -> ExternalDocument:
        subdomain = config.get("subdomain", "").strip()
        if not subdomain:
            raise ValueError("Subdomain is required")

        email = config.get("email", "").strip()
        if not email:
            raise ValueError("Email is required")

        access_token = config.get("apiKey")
        if not access_token:
            raise ValueError("API Token is required")

        base_url = self._build_base_url(subdomain)

        if external_id.startswith("article-"):
            article_id = external_id.replace("article-", "")
            url = f"{base_url}/api/v2/help_center/articles/{article_id}.json"
            data = await self._api_get(url, access_token, email)
            article = data.get("article")
            if not article:
                raise ValueError(f"Article not found: {article_id}")
            return await self._article_to_document(article, subdomain)

        if external_id.startswith("ticket-"):
            ticket_id = external_id.replace("ticket-", "")
            url = f"{base_url}/api/v2/tickets/{ticket_id}.json"
            data = await self._api_get(url, access_token, email)
            ticket = data.get("ticket")
            if not ticket:
                raise ValueError(f"Ticket not found: {ticket_id}")
            comments = await self._fetch_ticket_comments(
                base_url, access_token, email, int(ticket_id)
            )
            return self._ticket_to_document(ticket, comments, subdomain)

        raise ValueError(f"Unknown external ID format: {external_id}")

    async def validate_config(self, config: Dict[str, Any]) -> None:
        subdomain = config.get("subdomain", "").strip()
        if not subdomain:
            raise ValueError("Subdomain is required")

        email = config.get("email", "").strip()
        if not email:
            raise ValueError("Email is required")

        access_token = config.get("apiKey")
        if not access_token:
            raise ValueError("API Token is required")

        base_url = self._build_base_url(subdomain)
        url = f"{base_url}/api/v2/users/me.json"
        await self._api_get(url, access_token, email)

    async def _fetch_articles(
        self, base_url: str, access_token: str, email: str, locale: str = ""
    ) -> List[Dict[str, Any]]:
        all_articles = []
        locale_path = f"/{locale}" if locale else ""
        page = 1
        while True:
            url = (
                f"{base_url}/api/v2/help_center{locale_path}/articles.json?"
                f"page={page}&per_page={ARTICLES_PER_PAGE}"
            )
            data = await self._api_get(url, access_token, email)
            articles = data.get("articles", [])
            if not articles:
                break
            all_articles.extend(articles)
            if not data.get("next_page"):
                break
            page += 1
        return all_articles

    async def _fetch_tickets(
        self,
        base_url: str,
        access_token: str,
        email: str,
        status_filter: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        all_tickets = []
        url = f"{base_url}/api/v2/tickets.json?per_page={TICKETS_PER_PAGE}"
        if status_filter and status_filter != "all":
            url = (
                f"{base_url}/api/v2/search.json?query=type:ticket "
                f"status:{status_filter}&per_page={TICKETS_PER_PAGE}"
            )

        while url and len(all_tickets) < limit:
            data = await self._api_get(url, access_token, email)
            tickets = data.get("tickets") or data.get("results") or []
            if not tickets:
                break
            all_tickets.extend(tickets)
            url = data.get("next_page")

        return all_tickets[:limit]

    async def _fetch_ticket_comments(
        self, base_url: str, access_token: str, email: str, ticket_id: int
    ) -> List[Dict[str, Any]]:
        all_comments = []
        url = (
            f"{base_url}/api/v2/tickets/{ticket_id}/comments.json?"
            "per_page=100"
        )
        while url:
            data = await self._api_get(url, access_token, email)
            comments = data.get("comments", [])
            all_comments.extend(comments)
            url = data.get("next_page")
        return all_comments

    async def _article_to_document(
        self, article: Dict[str, Any], subdomain: str
    ) -> ExternalDocument:
        content = html_to_plain_text(article.get("body", ""))
        return ExternalDocument(
            externalId=f"article-{article['id']}",
            title=article.get("title") or f"Article {article['id']}",
            content=content,
            mimeType="text/plain",
            sourceUrl=(
                article.get("html_url")
                or f"https://{subdomain}.zendesk.com/hc/articles/{article['id']}"
            ),
            contentHash=compute_content_hash(content),
            metadata={
                "type": "article",
                "articleId": article["id"],
                "sectionId": article.get("section_id"),
                "labels": article.get("label_names", []),
                "author": str(article.get("author_id")),
                "locale": article.get("locale"),
                "draft": article.get("draft"),
                "createdAt": article.get("created_at"),
                "updatedAt": article.get("updated_at"),
            },
        )

    def _ticket_to_document(
        self, ticket: Dict[str, Any], comments: List[Dict[str, Any]], subdomain: str
    ) -> ExternalDocument:
        content = self._format_ticket_content(ticket, comments)
        return ExternalDocument(
            externalId=f"ticket-{ticket['id']}",
            title=f"Ticket #{ticket['id']}: {ticket.get('subject', '')}",
            content=content,
            mimeType="text/plain",
            sourceUrl=f"https://{subdomain}.zendesk.com/agent/tickets/{ticket['id']}",
            contentHash=compute_content_hash(content),
            metadata={
                "type": "ticket",
                "ticketId": ticket["id"],
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "tags": ticket.get("tags", []),
                "commentCount": len(comments),
                "createdAt": ticket.get("created_at"),
                "updatedAt": ticket.get("updated_at"),
            },
        )

    def _format_ticket_content(
        self, ticket: Dict[str, Any], comments: List[Dict[str, Any]]
    ) -> str:
        parts = []
        parts.append(f"Subject: {ticket.get('subject', '')}")
        parts.append(f"Status: {ticket.get('status', '')}")
        if ticket.get("priority"):
            parts.append(f"Priority: {ticket['priority']}")
        parts.append(f"Created: {ticket.get('created_at', '')}")
        parts.append(f"Updated: {ticket.get('updated_at', '')}")
        if ticket.get("tags"):
            parts.append(f"Tags: {', '.join(ticket['tags'])}")

        parts.append("")
        parts.append("--- Description ---")
        parts.append(html_to_plain_text(ticket.get("description", "")))

        if comments:
            parts.append("")
            parts.append("--- Comments ---")
            for comment in comments:
                visibility = "Public" if comment.get("public") else "Internal"
                parts.append(
                    f"\n[{comment.get('created_at')}] ({visibility}) "
                    f"Author {comment.get('author_id')}:"
                )
                parts.append(html_to_plain_text(comment.get("body", "")))

        return "\n".join(parts)
