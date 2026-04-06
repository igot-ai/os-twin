import httpx
import logging
import asyncio
import json
from typing import Dict, Any, Optional, List, Union
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

logger = logging.getLogger(__name__)

ASANA_API = "https://app.asana.com/api/1.0"
TASK_OPT_FIELDS = "name,notes,completed,completed_at,modified_at,assignee.name,tags.name,permalink_url"

def build_task_content(task: Dict[str, Any]) -> str:
    parts = []
    parts.append(task.get("name") or "Untitled")
    
    assignee = task.get("assignee")
    if assignee and isinstance(assignee, dict) and assignee.get("name"):
        parts.append(f"Assignee: {assignee['name']}")
    
    parts.append(f"Completed: {'Yes' if task.get('completed') else 'No'}")
    
    tags = task.get("tags")
    if isinstance(tags, list):
        tag_names = [t.get("name") for t in tags if isinstance(t, dict) and t.get("name")]
        if tag_names:
            parts.append(f"Labels: {', '.join(tag_names)}")
    
    notes = task.get("notes")
    if notes:
        parts.append("")
        parts.append(notes)
    
    return "\n".join(parts)

async def list_workspace_projects(client: ConnectorHttpClient, workspace_gid: str) -> List[Dict[str, Any]]:
    projects = []
    offset = None
    while True:
        params = {"workspace": workspace_gid, "limit": 100}
        if offset:
            params["offset"] = offset
        
        response = await client.get("/projects", params=params)
        response.raise_for_status()
        data = response.json()
        projects.extend(data.get("data", []))
        
        next_page = data.get("next_page")
        if not next_page:
            break
        offset = next_page.get("offset")
    
    return projects

@registry.register
class AsanaConnector(BaseConnector):
    @property
    def config(self) -> ConnectorConfig:
        return ConnectorConfig(
            id="asana",
            name="Asana",
            description="Sync tasks from Asana into your knowledge base",
            version="1.0.0",
            icon="asana",
            auth_config=OAuthAuthConfig(
                mode="oauth",
                provider="asana",
                required_scopes=["default"],
            ),
            config_fields=[
                ConnectorConfigField(
                    id="workspaceSelector",
                    title="Workspace",
                    type="selector",
                    selector_key="asana.workspaces",
                    canonical_param_id="workspace",
                    mode="basic",
                    placeholder="Select a workspace",
                    required=True,
                ),
                ConnectorConfigField(
                    id="workspace",
                    title="Workspace GID",
                    type="short-input",
                    canonical_param_id="workspace",
                    mode="advanced",
                    placeholder="e.g. 1234567890",
                    required=True,
                ),
                ConnectorConfigField(
                    id="project",
                    title="Project GID",
                    type="short-input",
                    placeholder="e.g. 9876543210 (leave empty for all projects)",
                    required=False,
                ),
                ConnectorConfigField(
                    id="maxTasks",
                    title="Max Tasks",
                    type="short-input",
                    placeholder="e.g. 500 (default: unlimited)",
                    required=False,
                ),
            ],
        )

    def _get_client(self, access_token: str) -> ConnectorHttpClient:
        return ConnectorHttpClient(
            base_url=ASANA_API,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
        )

    async def list_documents(
        self, config: Dict[str, Any], cursor: Optional[str] = None
    ) -> ExternalDocumentList:
        access_token = config.get("accessToken")
        workspace_gid = config.get("workspace")
        project_gid = config.get("project", "")
        max_tasks = int(config.get("maxTasks")) if config.get("maxTasks") else 0
        page_size = min(max_tasks, 100) if max_tasks > 0 else 100
        
        client = self._get_client(access_token)
        
        project_gids = []
        project_index = 0
        offset = None
        
        if project_gid:
            project_gids = [project_gid]
        else:
            if not config.get("projectGids"):
                projects = await list_workspace_projects(client, workspace_gid)
                project_gids = [p["gid"] for p in projects]
                config["projectGids"] = project_gids
            else:
                project_gids = config["projectGids"]
        
        if cursor:
            try:
                parsed = json.loads(cursor)
                project_index = parsed.get("projectIndex", 0)
                offset = parsed.get("offset")
            except json.JSONDecodeError:
                offset = cursor
        
        documents = []
        next_cursor = None
        has_more = False
        
        while project_index < len(project_gids):
            current_project_gid = project_gids[project_index]
            params = {
                "project": current_project_gid,
                "opt_fields": TASK_OPT_FIELDS,
                "limit": page_size
            }
            if offset:
                params["offset"] = offset
            
            response = await client.get("/tasks", params=params)
            response.raise_for_status()
            data = response.json()
            
            for task in data.get("data", []):
                content = build_task_content(task)
                content_hash = compute_content_hash(content)
                tag_names = [t.get("name") for t in task.get("tags", []) if isinstance(t, dict) and t.get("name")]
                
                documents.append(ExternalDocument(
                    external_id=task["gid"],
                    title=task.get("name") or "Untitled",
                    content=content,
                    mime_type="text/plain",
                    source_url=task.get("permalink_url"),
                    content_hash=content_hash,
                    metadata={
                        "project": current_project_gid,
                        "assignee": task.get("assignee", {}).get("name") if isinstance(task.get("assignee"), dict) else None,
                        "completed": task.get("completed"),
                        "lastModified": task.get("modified_at"),
                        "labels": tag_names,
                    }
                ))
            
            next_page = data.get("next_page")
            if next_page:
                next_cursor = json.dumps({"projectIndex": project_index, "offset": next_page.get("offset")})
                has_more = True
                break
            
            project_index += 1
            offset = None
            if project_index < len(project_gids):
                next_cursor = json.dumps({"projectIndex": project_index, "offset": None})
                has_more = True
                break
        
        previously_fetched = config.get("totalDocsFetched", 0)
        if max_tasks > 0:
            remaining = max_tasks - previously_fetched
            if len(documents) > remaining:
                documents = documents[:remaining]
        
        total_fetched = previously_fetched + len(documents)
        config["totalDocsFetched"] = total_fetched
        
        if max_tasks > 0 and total_fetched >= max_tasks:
            has_more = False
            next_cursor = None
            
        return ExternalDocumentList(
            documents=documents,
            next_cursor=next_cursor,
            has_more=has_more
        )

    async def get_document(
        self, external_id: str, config: Dict[str, Any]
    ) -> ExternalDocument:
        access_token = config.get("accessToken")
        client = self._get_client(access_token)
        
        response = await client.get(f"/tasks/{external_id}", params={"opt_fields": TASK_OPT_FIELDS})
        if response.status_code == 404:
            raise Exception(f"Asana task {external_id} not found")
        response.raise_for_status()
        
        data = response.json()
        task = data.get("data")
        if not task:
            raise Exception(f"Asana task {external_id} not found")
            
        content = build_task_content(task)
        content_hash = compute_content_hash(content)
        tag_names = [t.get("name") for t in task.get("tags", []) if isinstance(t, dict) and t.get("name")]
        
        return ExternalDocument(
            external_id=task["gid"],
            title=task.get("name") or "Untitled",
            content=content,
            mime_type="text/plain",
            source_url=task.get("permalink_url"),
            content_hash=content_hash,
            metadata={
                "assignee": task.get("assignee", {}).get("name") if isinstance(task.get("assignee"), dict) else None,
                "completed": task.get("completed"),
                "lastModified": task.get("modified_at"),
                "labels": tag_names,
            }
        )

    async def validate_config(self, config: Dict[str, Any]) -> None:
        access_token = config.get("accessToken")
        workspace_gid = config.get("workspace")
        if not workspace_gid:
            raise ValueError("Workspace GID is required")
            
        max_tasks = config.get("maxTasks")
        if max_tasks:
            try:
                if int(max_tasks) <= 0:
                    raise ValueError()
            except ValueError:
                raise ValueError("Max tasks must be a positive number")

        client = self._get_client(access_token)
        response = await client.get(f"/workspaces/{workspace_gid}")
        if response.status_code != 200:
            raise Exception(f"Asana API error: {response.status_code}")
