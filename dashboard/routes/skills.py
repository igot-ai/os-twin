import os
import logging
import re
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query

from dashboard.models import Skill, SkillInstallRequest, SkillSearchRequest, SkillSyncResponse
from dashboard.api_utils import SKILLS_DIRS, AGENTS_DIR, PROJECT_ROOT, parse_skill_md, build_skills_list
import dashboard.global_state as global_state
from dashboard.auth import get_current_user

router = APIRouter(tags=["skills"])
logger = logging.getLogger(__name__)

@router.get("/api/skills", response_model=List[Skill])
async def list_skills(
    role: Optional[str] = None, 
    tags: List[str] = Query([]),
    user: dict = Depends(get_current_user)
):
    """List all available skills with optional filtering."""
    return build_skills_list(role=role, tags=tags)

@router.get("/api/skills/search", response_model=List[Skill])
async def search_skills_endpoint(
    q: str = Query(..., description="Semantic search query"),
    role: Optional[str] = None,
    tags: List[str] = Query([]),
    user: dict = Depends(get_current_user)
):
    """Semantic search for skills with role-based post-filtering."""
    return build_skills_list(query=q, role=role, tags=tags)

@router.get("/api/skills/{name}", response_model=Skill)
async def get_skill(name: str, user: dict = Depends(get_current_user)):
    """Fetch details for a specific skill."""
    store = global_state.store
    if store:
        data = store.get_skill(name)
        if data:
            return Skill(**data)
    
    # Check on disk
    for sdir in SKILLS_DIRS:
        # Search recursively for the skill folder
        for path in sdir.rglob(name):
            if path.is_dir() and (path / "SKILL.md").exists():
                data = parse_skill_md(path)
                if data:
                    return Skill(**data)
                
    raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")

@router.post("/api/skills/install")
async def install_skill(req: SkillInstallRequest, user: dict = Depends(get_current_user)):
    """Install a new skill from a local filesystem path."""
    path = Path(req.path)
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Path does not exist or is not a directory")
    
    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        raise HTTPException(status_code=400, detail="Directory must contain a valid SKILL.md file")
    
    data = parse_skill_md(path)
    if not data:
        raise HTTPException(status_code=400, detail="Failed to parse SKILL.md")
    
    store = global_state.store
    if store:
        store.index_skill(
            name=data["name"],
            description=data["description"],
            tags=data["tags"],
            path=data["path"],
            relative_path=data.get("relative_path", ""),
            trust_level=data["trust_level"],
            source=data["source"],
            content=data["content"]
        )
            
    return {"status": "installed", "skill": data["name"]}

@router.post("/api/skills/sync", response_model=SkillSyncResponse)
async def sync_skills_endpoint(user: dict = Depends(get_current_user)):
    """Synchronize the vector database with on-disk skills directories."""
    store = global_state.store
    if not store:
        raise HTTPException(status_code=503, detail="Vector store not available")
    
    result = store.sync_skills(SKILLS_DIRS)
    return SkillSyncResponse(**result)

@router.get("/api/skills/tags", response_model=List[str])
async def list_skill_tags(user: dict = Depends(get_current_user)):
    """List all unique tags across all available skills."""
    skills = build_skills_list()
    tags = set()
    for s in skills:
        for t in s.tags:
            tags.add(t)
    return sorted(list(tags))
