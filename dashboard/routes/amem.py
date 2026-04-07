"""Dashboard API routes for Agentic Memory (A-mem-sys).

Reads .memory/ directory from the plan's working_dir to serve
graph snapshots, memory notes, and search results to the frontend.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pathlib import Path
from typing import Optional
import json
import os
import re

from dashboard.api_utils import PLANS_DIR
from dashboard.auth import get_current_user

router = APIRouter(tags=["amem"])


def _resolve_memory_dir(plan_id: str) -> Path:
    """Resolve .memory/ directory from a plan's working_dir."""
    meta_file = PLANS_DIR / f"{plan_id}.meta.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
        working_dir = meta.get("working_dir", "")
        if working_dir:
            mem_dir = Path(working_dir) / ".memory"
            if mem_dir.exists():
                return mem_dir

    # Fallback: try to parse working_dir from the plan .md file
    plan_file = PLANS_DIR / f"{plan_id}.md"
    if plan_file.exists():
        content = plan_file.read_text()
        match = re.search(r"working_dir:\s*(.+)", content)
        if match:
            working_dir = match.group(1).strip()
            mem_dir = Path(working_dir) / ".memory"
            if mem_dir.exists():
                return mem_dir

    raise HTTPException(status_code=404, detail=f"No .memory/ found for plan {plan_id}")


def _load_notes(notes_dir: Path) -> list:
    """Load all markdown notes from the notes directory."""
    notes = []
    if not notes_dir.exists():
        return notes

    for md_file in sorted(notes_dir.rglob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
            rel_path = str(md_file.relative_to(notes_dir))

            note = {
                "id": md_file.stem,
                "filename": md_file.name,
                "path": str(md_file.parent.relative_to(notes_dir)),
                "relativePath": rel_path,
                "content": content,
                "title": md_file.stem.replace("-", " ").title(),
                "tags": [],
                "keywords": [],
                "links": [],
                "excerpt": "",
            }

            # Extract title from first H1
            title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
            if title_match:
                note["title"] = title_match.group(1).strip()

            # Extract tags
            tags_match = re.search(r"\*\*Tags\*\*:\s*(.+)", content)
            if tags_match:
                note["tags"] = [t.strip().lstrip("#") for t in tags_match.group(1).split(",")]

            # Extract keywords
            kw_match = re.search(r"\*\*Keywords\*\*:\s*(.+)", content)
            if kw_match:
                note["keywords"] = [k.strip() for k in kw_match.group(1).split(",")]

            # Extract links
            links_match = re.search(r"\*\*Links\*\*:\s*(.+)", content)
            if links_match:
                raw = links_match.group(1).strip()
                if raw and raw != "None":
                    note["links"] = [l.strip() for l in raw.split(",") if l.strip()]

            # Build excerpt
            lines = content.split("\n")
            body_lines = [l for l in lines if not l.startswith("**") and not l.startswith("#") and l.strip()]
            note["excerpt"] = " ".join(body_lines)[:250]

            notes.append(note)
        except Exception:
            continue

    return notes


GRAPH_GROUP_COLORS = [
    "#8b5cf6", "#facc15", "#2563eb", "#d4d4d8",
    "#16a34a", "#ff5d5d", "#14b8a6", "#f97316",
]


def _build_graph(notes: list) -> dict:
    """Build a graph visualization from notes."""
    groups = {}
    nodes = []
    links = []
    note_ids = {n["id"] for n in notes}

    for note in notes:
        path_parts = note["path"].split("/") if note["path"] != "." else ["unfiled"]
        group_key = path_parts[0] if path_parts else "unfiled"

        if group_key not in groups:
            color = GRAPH_GROUP_COLORS[len(groups) % len(GRAPH_GROUP_COLORS)]
            groups[group_key] = {
                "id": group_key,
                "label": group_key.replace("-", " ").replace("_", " ").title(),
                "query": f'path:"{group_key}/"',
                "color": color,
                "pathPrefix": group_key,
                "description": f"Notes in {group_key}",
            }

        color = groups[group_key]["color"]
        connections = len(note.get("links", []))

        nodes.append({
            "id": note["id"],
            "title": note["title"],
            "path": note["relativePath"],
            "pathLabel": note["path"],
            "excerpt": note["excerpt"],
            "content": note["content"],
            "summary": note["excerpt"][:150],
            "keywords": note["keywords"],
            "tags": note["tags"],
            "groupId": group_key,
            "color": color,
            "weight": 1.0 + min(2.0, connections * 0.3),
            "connections": connections,
        })

        for link_id in note.get("links", []):
            if link_id in note_ids:
                links.append({
                    "source": note["id"],
                    "target": link_id,
                    "strength": 0.5,
                })

    return {
        "groups": list(groups.values()),
        "nodes": nodes,
        "links": links,
        "stats": {
            "total_memories": len(nodes),
            "total_links": len(links),
            "total_groups": len(groups),
        },
    }


@router.get("/api/amem/{plan_id}/graph")
async def get_memory_graph(plan_id: str, user: dict = Depends(get_current_user)):
    """Get the memory graph for a plan's project."""
    mem_dir = _resolve_memory_dir(plan_id)
    notes_dir = mem_dir / "notes"
    notes = _load_notes(notes_dir)
    return _build_graph(notes)


@router.get("/api/amem/{plan_id}/notes")
async def list_memory_notes(plan_id: str, user: dict = Depends(get_current_user)):
    """List all memory notes for a plan's project."""
    mem_dir = _resolve_memory_dir(plan_id)
    notes_dir = mem_dir / "notes"
    notes = _load_notes(notes_dir)
    for n in notes:
        n.pop("content", None)
    return notes


@router.get("/api/amem/{plan_id}/notes/{note_id}")
async def get_memory_note(plan_id: str, note_id: str, user: dict = Depends(get_current_user)):
    """Get a single memory note by ID."""
    mem_dir = _resolve_memory_dir(plan_id)
    notes_dir = mem_dir / "notes"
    notes = _load_notes(notes_dir)
    for note in notes:
        if note["id"] == note_id:
            return note
    raise HTTPException(status_code=404, detail=f"Note {note_id} not found")


@router.get("/api/amem/{plan_id}/stats")
async def get_memory_stats(plan_id: str, user: dict = Depends(get_current_user)):
    """Get memory statistics for a plan's project."""
    mem_dir = _resolve_memory_dir(plan_id)
    notes_dir = mem_dir / "notes"
    notes = _load_notes(notes_dir)

    tags = set()
    keywords = set()
    paths = set()
    for n in notes:
        tags.update(n.get("tags", []))
        keywords.update(n.get("keywords", []))
        paths.add(n.get("path", ""))

    return {
        "total_notes": len(notes),
        "total_tags": len(tags),
        "total_keywords": len(keywords),
        "total_paths": len(paths),
        "memory_dir": str(mem_dir),
        "tags": sorted(tags),
        "paths": sorted(paths),
    }
