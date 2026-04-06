import httpx
import urllib.parse
from typing import Dict, Any, Optional, List
from datetime import datetime
from .base import BaseConnector
from .models import (
    ConnectorConfig,
    ExternalDocument,
    ExternalDocumentList,
    ApiKeyAuthConfig,
    ConnectorConfigField,
)
from .registry import registry

DOCS_PER_PAGE = 50
MAX_RECURSION_DEPTH = 20


@registry.register
class ObsidianConnector(BaseConnector):
    @property
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(
            id="obsidian",
            name="Obsidian",
            description=(
                "Sync notes from an Obsidian vault via the Local REST API plugin"
            ),
            version="1.0.0",
            icon="obsidian",
            auth_config=ApiKeyAuthConfig(
                mode="apiKey",
                label="API Key",
                placeholder="Enter your Obsidian Local REST API key",
            ),
            config_fields=[
                ConnectorConfigField(
                    id="vaultUrl",
                    title="Vault URL",
                    type="short-input",
                    placeholder="https://127.0.0.1:27124",
                    required=True,
                    description=(
                        "Base URL of your Obsidian Local REST API "
                        "(default port: 27124 for HTTPS)"
                    ),
                ),
                ConnectorConfigField(
                    id="folderPath",
                    title="Folder Path",
                    type="short-input",
                    placeholder="e.g. Projects/Notes",
                    required=False,
                    description=(
                        "Only sync notes from this folder "
                        "(leave empty for entire vault)"
                    ),
                ),
            ],
        )

    def _normalize_url(self, url: str) -> str:
        return url.strip().rstrip("/")

    def _title_from_path(self, file_path: str) -> str:
        filename = file_path.split("/")[-1]
        if filename.endswith(".md"):
            return filename[:-3]
        return filename

    def _encode_path(self, file_path: str) -> str:
        return "/".join(
            urllib.parse.quote(part, safe="") for part in file_path.split("/")
        )

    async def _api_get(
        self, url: str, access_token: str, headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        default_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        if headers:
            default_headers.update(headers)
        async with httpx.AsyncClient(
            verify=False  # nosec B501 - Local API often uses self-signed certs
        ) as client:
            return await client.get(url, headers=default_headers)

    async def _list_directory(
        self, base_url: str, access_token: str, dir_path: str
    ) -> List[str]:
        encoded_dir = self._encode_path(dir_path)
        endpoint = (
            f"{base_url}/vault/{encoded_dir}/" if encoded_dir else f"{base_url}/vault/"
        )
        response = await self._api_get(endpoint, access_token)
        if response.status_code != 200:
            raise Exception(
                f"Obsidian API error: {response.status_code} {response.text}"
            )
        data = response.json()
        return data.get("files", [])

    async def _list_vault_files(
        self, base_url: str, access_token: str, folder_path: str = "", depth: int = 0
    ) -> List[str]:
        if depth > MAX_RECURSION_DEPTH:
            return []

        entries = await self._list_directory(base_url, access_token, folder_path)
        md_files = []
        sub_dirs = []

        for entry in entries:
            if entry.endswith("/"):
                full_dir = f"{folder_path}/{entry[:-1]}" if folder_path else entry[:-1]
                sub_dirs.append(full_dir)
            elif entry.endswith(".md"):
                full_path = f"{folder_path}/{entry}" if folder_path else entry
                md_files.append(full_path)

        for dir_path in sub_dirs:
            try:
                nested = await self._list_vault_files(
                    base_url, access_token, dir_path, depth + 1
                )
                md_files.extend(nested)
            except Exception as e:
                # Log error and continue
                print(f"Error listing nested Obsidian directory {dir_path}: {e}")
                continue

        return md_files

    async def list_documents(
        self, config: Dict[str, Any], cursor: Optional[str] = None
    ) -> ExternalDocumentList:
        access_token = config.get("apiKey")
        base_url = self._normalize_url(
            config.get("vaultUrl", "https://127.0.0.1:27124")
        )
        folder_path = config.get("folderPath", "").strip()

        all_files = await self._list_vault_files(base_url, access_token, folder_path)

        offset = int(cursor) if cursor else 0
        page_files = all_files[offset : offset + DOCS_PER_PAGE]

        documents = []
        for file_path in page_files:
            encoded_path = self._encode_path(file_path)
            documents.append(
                ExternalDocument(
                    externalId=file_path,
                    title=self._title_from_path(file_path),
                    content="",
                    contentDeferred=True,
                    mimeType="text/plain",
                    sourceUrl=f"{base_url}/vault/{encoded_path}",
                    contentHash=f"obsidian:stub:{file_path}",
                    metadata={
                        "folder": file_path.rsplit("/", 1)[0]
                        if "/" in file_path
                        else ""
                    },
                )
            )

        next_offset = offset + len(page_files)
        has_more = next_offset < len(all_files)

        return ExternalDocumentList(
            documents=documents,
            nextCursor=str(next_offset) if has_more else None,
            hasMore=has_more,
        )

    async def get_document(
        self, external_id: str, config: Dict[str, Any]
    ) -> ExternalDocument:
        access_token = config.get("apiKey")
        base_url = self._normalize_url(
            config.get("vaultUrl", "https://127.0.0.1:27124")
        )

        encoded_path = self._encode_path(external_id)
        url = f"{base_url}/vault/{encoded_path}"
        headers = {"Accept": "application/vnd.olrapi.note+json"}

        response = await self._api_get(url, access_token, headers=headers)
        if response.status_code != 200:
            raise Exception(
                f"Obsidian API error fetching {external_id}: {response.status_code}"
            )

        note = response.json()
        content = note.get("content", "")
        stat = note.get("stat", {})

        return ExternalDocument(
            externalId=external_id,
            title=self._title_from_path(external_id),
            content=content,
            contentDeferred=False,
            mimeType="text/plain",
            sourceUrl=f"{base_url}/vault/{encoded_path}",
            contentHash=f"obsidian:{external_id}:{stat.get('mtime', '')}",
            metadata={
                "tags": note.get("tags", []),
                "frontmatter": note.get("frontmatter", {}),
                "createdAt": datetime.fromtimestamp(stat["ctime"] / 1000).isoformat()
                if stat.get("ctime")
                else None,
                "modifiedAt": datetime.fromtimestamp(stat["mtime"] / 1000).isoformat()
                if stat.get("mtime")
                else None,
                "size": stat.get("size"),
                "folder": external_id.rsplit("/", 1)[0] if "/" in external_id else "",
            },
        )

    async def validate_config(self, config: Dict[str, Any]) -> None:
        access_token = config.get("apiKey")
        if not access_token:
            raise ValueError("API Key is required")

        vault_url = config.get("vaultUrl")
        if not vault_url or not vault_url.strip():
            raise ValueError("Vault URL is required")

        base_url = self._normalize_url(vault_url)

        try:
            response = await self._api_get(f"{base_url}/", access_token)
            if response.status_code in [401, 403]:
                raise ValueError(
                    "Invalid API key — check your Obsidian Local REST API settings"
                )
            if response.status_code != 200:
                raise ValueError(f"Obsidian API returned status {response.status_code}")

            folder_path = config.get("folderPath", "").strip()
            if folder_path:
                await self._list_directory(base_url, access_token, folder_path)
        except httpx.RequestError as e:
            raise ValueError(f"Failed to connect to Obsidian vault: {str(e)}")
