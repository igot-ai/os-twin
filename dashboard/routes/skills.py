import os
import logging
import re
from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query

from dashboard.models import (
    Skill, SkillInstallRequest, SkillSyncResponse,
    SkillCreateRequest, SkillUpdateRequest, SkillForkRequest,
    SkillValidateRequest, SkillValidateResponse,
    SkillDuplicateCheckRequest, SkillDuplicateCheckResponse
)
from dashboard.api_utils import (
    SKILLS_DIRS, AGENTS_DIR, PROJECT_ROOT, 
    parse_skill_md, build_skills_list, save_skill_md,
    get_active_epics_using_skill
)
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
    skills = build_skills_list(role=role, tags=tags, include_drafts=True)
    # Filter drafts: published skills are visible to all; drafts only to author
    current_username = user.get("username", "unknown")
    return [
        s for s in skills 
        if not s.is_draft or s.author == current_username
    ]

@router.get("/api/skills/search", response_model=List[Skill])
async def search_skills_endpoint(
    q: str = Query(..., description="Semantic search query"),
    role: Optional[str] = None,
    tags: List[str] = Query([]),
    limit: int = Query(50, ge=1, le=100, description="Max results to return"),
    user: dict = Depends(get_current_user)
):
    """Semantic search for skills with role-based post-filtering."""
    skills = build_skills_list(query=q, role=role, tags=tags, limit=limit, include_drafts=True)
    current_username = user.get("username", "unknown")
    return [
        s for s in skills 
        if not s.is_draft or s.author == current_username
    ]

@router.get("/api/skills/tags", response_model=List[str])
async def list_skill_tags(user: dict = Depends(get_current_user)):
    """List all unique tags across all available skills."""
    skills = build_skills_list()
    tags = set()
    for s in skills:
        for t in s.tags:
            tags.add(t)
    return sorted(list(tags))

@router.get("/api/skills/roles", response_model=List[str])
async def list_skill_roles(user: dict = Depends(get_current_user)):
    """List all available roles from the registry."""
    from dashboard.api_utils import build_roles_list
    roles = build_roles_list({}) # Empty config to get all registry roles
    return [r["name"] for r in roles]

@router.get("/api/skills/{name}", response_model=Skill)
async def get_skill(name: str, user: dict = Depends(get_current_user)):
    """Fetch details for a specific skill."""
    store = global_state.store
    skill_data = None
    
    if store:
        skill_data = store.get_skill(name)
    
    if not skill_data:
        # Check on disk
        # Normalize name for file search
        folder_name = name.lower().replace(" ", "-")
        for sdir in SKILLS_DIRS:
            # Search recursively for the skill folder
            for path in sdir.rglob(folder_name):
                if path.is_dir() and (path / "SKILL.md").exists():
                    skill_data = parse_skill_md(path)
                    break
            if skill_data: break
                
    if not skill_data:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
        
    skill = Skill(**skill_data)
    skill.active_epics_count = get_active_epics_using_skill(skill.name)
    return skill

@router.get("/api/skills/{name}/versions/{version}")
async def get_skill_version(name: str, version: str, user: dict = Depends(get_current_user)):
    """Fetch raw instruction template for a historical version of a skill."""
    # Handle folder name normalization
    folder_name = name.lower().replace(" ", "-")
    
    for sdir in SKILLS_DIRS:
        # Search for the skill directory
        for path in sdir.rglob(folder_name):
            if path.is_dir() and (path / "SKILL.md").exists():
                # If requesting current version, just return current
                current_data = parse_skill_md(path)
                if current_data and current_data.get("version") == version:
                    return {"content": current_data.get("content", "")}

                # Check .versions folder
                version_filename = f"v{version}.md"
                version_file = path / ".versions" / version_filename
                if version_file.exists():
                    historical_data = parse_skill_md(path, filename=f".versions/{version_filename}")
                    if historical_data:
                        return {"content": historical_data.get("content", "")}
                    
    raise HTTPException(status_code=404, detail=f"Version {version} of skill '{name}' not found")

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

from datetime import datetime, timezone
@router.post("/api/skills", response_model=Skill)
async def create_skill(req: SkillCreateRequest, user: dict = Depends(get_current_user)):
    """Create a new custom skill."""
    # Check for name uniqueness
    existing = build_skills_list()
    if any(s.name.lower() == req.name.lower() for s in existing):
        raise HTTPException(status_code=400, detail=f"Skill with name '{req.name}' already exists")
    
    timestamp = datetime.now(timezone.utc).timestamp()
    skill_data = {
        "name": req.name,
        "description": req.description,
        "category": req.category,
        "applicable_roles": req.applicable_roles,
        "tags": req.tags,
        "content": req.content,
        "is_draft": req.is_draft,
        "author": user.get("username", "unknown"),
        "version": "1.0.0" if not req.is_draft else "0.1.0",
        "changelog": [{"version": "1.0.0" if not req.is_draft else "0.1.0", "date": timestamp, "changes": "Initial creation"}]
    }
    
    path = save_skill_md(skill_data)
    indexed_data = parse_skill_md(path)
    
    store = global_state.store
    if store:
        store.index_skill(**indexed_data)
        
    return Skill(**indexed_data)

@router.put("/api/skills/{name}", response_model=Skill)
async def update_skill(name: str, req: SkillUpdateRequest, user: dict = Depends(get_current_user)):
    """Update an existing skill."""
    # Fetch existing skill
    skill_data = await get_skill(name, user)
    if not skill_data:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    
    skill_dict = skill_data.dict()
    
    # Apply updates
    if req.description is not None: skill_dict["description"] = req.description
    if req.category is not None: skill_dict["category"] = req.category
    if req.applicable_roles is not None: skill_dict["applicable_roles"] = req.applicable_roles
    if req.tags is not None: skill_dict["tags"] = req.tags
    if req.content is not None: skill_dict["content"] = req.content
    if req.is_draft is not None: skill_dict["is_draft"] = req.is_draft
    
    # Version bump logic
    current_version = skill_dict.get("version", "1.0.0")
    major, minor, patch = map(int, current_version.split("."))
    if req.major_bump:
        new_version = f"{major + 1}.0.0"
    else:
        new_version = f"{major}.{minor + 1}.0"
    
    skill_dict["version"] = new_version
    
    # Add changelog entry
    changelog = skill_dict.get("changelog", [])
    timestamp = datetime.now(timezone.utc).timestamp()
    changelog.insert(0, {
        "version": new_version,
        "date": timestamp,
        "changes": req.change_description or "Manual update"
    })
    skill_dict["changelog"] = changelog
    
    # Save back to disk
    path = Path(skill_dict["path"])
    save_skill_md(skill_dict, path=path)
    
    # Update index
    store = global_state.store
    if store:
        indexed_data = parse_skill_md(path)
        store.index_skill(**indexed_data)
        return Skill(**indexed_data)
        
    return Skill(**skill_dict)

@router.post("/api/skills/{name}/fork", response_model=Skill)
async def fork_skill(name: str, req: SkillForkRequest, user: dict = Depends(get_current_user)):
    """Fork an existing skill."""
    original = await get_skill(name, user)
    if not original:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
        
    # Check for name uniqueness
    existing = build_skills_list()
    if any(s.name.lower() == req.name.lower() for s in existing):
        raise HTTPException(status_code=400, detail=f"Skill with name '{req.name}' already exists")

    fork_data = original.dict()
    fork_data["name"] = req.name
    fork_data["version"] = "1.0.0"
    fork_data["author"] = user.get("username", "unknown")
    fork_data["forked_from"] = name
    timestamp = datetime.now(timezone.utc).timestamp()
    fork_data["changelog"] = [{"version": "1.0.0", "date": timestamp, "changes": f"Forked from {name}"}]
    fork_data.pop("path", None)
    fork_data.pop("relative_path", None)
    
    path = save_skill_md(fork_data)
    indexed_data = parse_skill_md(path)
    
    store = global_state.store
    if store:
        store.index_skill(**indexed_data)
        
    return Skill(**indexed_data)

@router.post("/api/skills/validate", response_model=SkillValidateResponse)
async def validate_skill_template(req: SkillValidateRequest, user: dict = Depends(get_current_user)):
    """Validate skill instruction template and return markers for editor."""
    content = req.content
    errors = []
    warnings = []
    markers = []
    
    # Known variables
    KNOWN_VARS = {"task_description", "working_dir", "definition_of_done", "acceptance_criteria", "previous_feedback"}
    
    # Simple line/col calculation helper
    def get_pos(offset):
        lines = content[:offset].split("\n")
        return len(lines), len(lines[-1]) + 1

    # Check for malformed brackets
    if content.count("{{") != content.count("}}"):
        errors.append("Malformed template variables: mismatched brackets '{{' and '}}'")
        # Heuristic markers for mismatched brackets
        for m in re.finditer(r"\{\{[^\}]*$", content, re.MULTILINE):
            line, col = get_pos(m.start())
            markers.append({
                "message": "Unclosed bracket '{{'",
                "severity": 8, # Error
                "startLineNumber": line,
                "startColumn": col,
                "endLineNumber": line,
                "endColumn": col + 2
            })
    
    # Check for unknown variables
    for m in re.finditer(r"\{\{([^}]+)\}\}", content):
        var = m.group(1).strip()
        if var not in KNOWN_VARS:
            line, col = get_pos(m.start())
            msg = f"Unknown template variable: '{{{{{var}}}}}'"
            warnings.append(msg)
            markers.append({
                "message": msg,
                "severity": 4, # Warning
                "startLineNumber": line,
                "startColumn": col,
                "endLineNumber": line,
                "endColumn": col + len(m.group(0))
            })
            
    # Check length
    if len(content) < 50:
        errors.append("Instruction template is too short (minimum 50 characters)")
        
    return SkillValidateResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        markers=markers
    )

@router.post("/api/skills/check-duplicate", response_model=SkillDuplicateCheckResponse)
async def check_duplicate_skill(req: SkillDuplicateCheckRequest, user: dict = Depends(get_current_user)):
    """Check for similar existing skills."""
    name = req.name.lower()
    existing_skills = build_skills_list()
    
    similar = []
    for s in existing_skills:
        if name in s.name.lower() or s.name.lower() in name:
            similar.append(s.name)
        # Simple Levenshtein substitute: check for high overlap or common words
        elif len(set(name.split()) & set(s.name.lower().split())) >= 2:
            similar.append(s.name)
            
    return SkillDuplicateCheckResponse(
        is_duplicate=any(s.name.lower() == name for s in existing_skills),
        similar_skills=similar[:5]
    )


