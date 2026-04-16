"""Dashboard API routes for Agentic Memory (A-mem-sys).

Reads .memory/ directory from the plan's working_dir to serve
graph snapshots, memory notes, and search results to the frontend.
"""

from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
from typing import Annotated, Optional
import json
import re
import sys

from dashboard.api_utils import PLANS_DIR
from dashboard.auth import get_current_user

# Reuse the canonical note parser from A-mem-sys instead of duplicating the
# YAML/frontmatter logic in the dashboard. We import from `memory_note`
# (not `memory_system`) to avoid pulling in the heavy retriever stack
# (sentence_transformers, chromadb, nltk, litellm) at dashboard startup.
_AMEM_PATH_CANDIDATES = [
    Path.home() / ".ostwin" / ".agents" / "memory",
    Path.home() / ".ostwin" / "A-mem-sys",
    Path(__file__).resolve().parent.parent.parent / ".agents" / "memory",
    Path(__file__).resolve().parent.parent.parent / "A-mem-sys",
]
for _p in _AMEM_PATH_CANDIDATES:
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from agentic_memory.memory_note import MemoryNote  # type: ignore
except ImportError:
    MemoryNote = None  # type: ignore

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


def _parse_legacy_metadata(text: str) -> tuple[list[str], list[str], list[str]]:
    """Extract Tags/Keywords/Links from **bold-label**: lines in raw markdown."""
    tags: list[str] = []
    keywords: list[str] = []
    links: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        for label, target in [
            ("**Tags**:", tags),
            ("**Keywords**:", keywords),
            ("**Links**:", links),
        ]:
            if stripped.startswith(label):
                value = stripped[len(label) :].strip()
                items = [v.strip().lstrip("#") for v in value.split(",") if v.strip()]
                target.extend(items)
    return tags, keywords, links


def _stub_note_dict(
    md_file: Path,
    rel_path: str,
    rel_file: str,
    body: str,
    raw: str,
) -> dict:
    """Build a minimal note dict when frontmatter parsing is unavailable."""
    tags, keywords, links = _parse_legacy_metadata(raw)
    title = _resolve_title(None, body, md_file)
    return {
        "id": md_file.stem,
        "filename": md_file.name,
        "path": rel_path,
        "relativePath": rel_file,
        "title": title,
        "body": body,
        "content": raw,
        "excerpt": body[:280],
        "tags": tags,
        "keywords": keywords,
        "links": links,
        "context": None,
        "summary": None,
        "category": None,
        "timestamp": None,
        "last_accessed": None,
        "retrieval_count": 0,
    }


def _extract_excerpt(body: str) -> str:
    """Build a short excerpt from body text, skipping headings and code fences."""
    excerpt_lines: list[str] = []
    in_code = False
    for ln in body.split("\n"):
        stripped = ln.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped or stripped.startswith("#"):
            continue
        excerpt_lines.append(stripped)
        if sum(len(s) for s in excerpt_lines) > 280:
            break
    return " ".join(excerpt_lines)[:280]


def _resolve_relative_paths(md_file: Path, notes_dir: Path) -> tuple[str, str]:
    """Compute relative path and relative file from a note's md_file."""
    try:
        rel_path = str(md_file.parent.relative_to(notes_dir))
        rel_file = str(md_file.relative_to(notes_dir))
    except ValueError:
        rel_path = md_file.parent.name
        rel_file = md_file.name
    return rel_path, rel_file


def _resolve_title(note_name: Optional[str], body: str, md_file: Path) -> str:
    """Derive a title from frontmatter name, first H1, or filename slug."""
    title = (note_name or "").strip()
    if not title:
        h1 = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        title = (
            h1.group(1).strip()
            if h1
            else md_file.stem.replace("-", " ").replace("_", " ").title()
        )
    return title


def _note_to_dict(md_file: Path, notes_dir: Path) -> Optional[dict]:
    """Read a single markdown file and convert it to the dashboard's wire shape.

    Delegates frontmatter parsing to ``MemoryNote.from_markdown`` so we share
    one parser with the rest of A-mem-sys. Falls back to a minimal stub if
    the import is unavailable (shouldn't happen at runtime, but defensive).
    """
    try:
        raw = md_file.read_text(encoding="utf-8")
    except OSError:
        return None

    rel_path, rel_file = _resolve_relative_paths(md_file, notes_dir)

    if MemoryNote is None:
        return _stub_note_dict(md_file, rel_path, rel_file, raw, raw)

    try:
        note = MemoryNote.from_markdown(raw)
    except ValueError:
        return _stub_note_dict(md_file, rel_path, rel_file, raw.strip(), raw)

    body = (note.content or "").strip()
    title = _resolve_title(note.name, body, md_file)
    category_val = (
        note.category if note.category and note.category != "Uncategorized" else None
    )

    return {
        "id": note.id,
        "filename": md_file.name,
        "path": rel_path,
        "relativePath": rel_file,
        "title": title,
        "body": body,
        "content": raw,
        "excerpt": _extract_excerpt(body),
        "tags": list(note.tags or []),
        "keywords": list(note.keywords or []),
        "links": list(note.links or []),
        "context": note.context if note.context and note.context != "General" else None,
        "summary": note.summary or None,
        "category": category_val,
        "timestamp": note.timestamp,
        "last_accessed": note.last_accessed,
        "retrieval_count": int(note.retrieval_count or 0),
    }


def _load_notes(notes_dir: Path) -> list:
    """Load all markdown notes from the notes directory.

    Each note's frontmatter is parsed by ``MemoryNote.from_markdown`` (the
    same code path A-mem-sys uses to write the file), so the dashboard sees
    exactly the structured fields the MCP server intended.
    """
    if not notes_dir.exists():
        return []
    notes = []
    for md_file in sorted(notes_dir.rglob("*.md")):
        d = _note_to_dict(md_file, notes_dir)
        if d is not None:
            notes.append(d)
    return notes


GRAPH_GROUP_COLORS = [
    "#8b5cf6",
    "#facc15",
    "#2563eb",
    "#d4d4d8",
    "#16a34a",
    "#ff5d5d",
    "#14b8a6",
    "#f97316",
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

        nodes.append(
            {
                "id": note["id"],
                "title": note["title"],
                "path": note["relativePath"],
                "pathLabel": note["path"],
                "excerpt": note["excerpt"],
                "body": note.get("body", ""),
                "content": note["content"],
                "summary": note.get("summary") or note["excerpt"][:150],
                "context": note.get("context"),
                "category": note.get("category"),
                "timestamp": note.get("timestamp"),
                "last_accessed": note.get("last_accessed"),
                "retrieval_count": note.get("retrieval_count", 0),
                "keywords": note["keywords"],
                "tags": note["tags"],
                "groupId": group_key,
                "color": color,
                "weight": 1.0 + min(2.0, connections * 0.3),
                "connections": connections,
            }
        )

        for link_id in note.get("links", []):
            if link_id in note_ids:
                links.append(
                    {
                        "source": note["id"],
                        "target": link_id,
                        "strength": 0.5,
                    }
                )

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


@router.get("/api/amem/{plan_id}/graph", responses={404: {"description": "Not found"}})
async def get_memory_graph(
    plan_id: str, user: Annotated[dict, Depends(get_current_user)] = None
):
    """Get the memory graph for a plan's project."""
    mem_dir = _resolve_memory_dir(plan_id)
    notes_dir = mem_dir / "notes"
    notes = _load_notes(notes_dir)
    return _build_graph(notes)


def _render_graph_png(graph_data: dict) -> bytes:
    """Render graph data as a PNG image. Runs in a thread (CPU-bound)."""
    import io
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx
    from matplotlib.patches import Patch

    G = nx.Graph()
    node_colors = []
    node_sizes = []
    labels = {}

    for node in graph_data["nodes"]:
        G.add_node(node["id"])
        node_colors.append(node.get("color", "#8b5cf6"))
        node_sizes.append(300 + node.get("connections", 0) * 150)
        title = node.get("title", node["id"])
        labels[node["id"]] = title[:25] + "..." if len(title) > 28 else title

    for link in graph_data["links"]:
        if G.has_node(link["source"]) and G.has_node(link["target"]):
            G.add_edge(link["source"], link["target"])

    fig, ax = plt.subplots(1, 1, figsize=(12, 8), facecolor="#0f0f0f")
    ax.set_facecolor("#0f0f0f")

    if len(G.nodes) > 1 and len(G.edges) > 0:
        pos = nx.spring_layout(G, k=2.5, iterations=60, seed=42)
    else:
        pos = nx.spring_layout(G, k=3.0, seed=42)

    nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#444444", width=1.5, alpha=0.6)
    nx.draw_networkx_nodes(
        G,
        pos,
        ax=ax,
        node_color=node_colors,
        node_size=node_sizes,
        edgecolors="#222222",
        linewidths=1.5,
        alpha=0.9,
    )
    nx.draw_networkx_labels(
        G,
        pos,
        labels=labels,
        ax=ax,
        font_size=8,
        font_color="white",
        font_weight="bold",
    )

    legend_handles = []
    for group in graph_data["groups"]:
        legend_handles.append(
            Patch(facecolor=group["color"], label=group["label"], alpha=0.9)
        )
    if legend_handles:
        legend = ax.legend(
            handles=legend_handles,
            loc="upper left",
            fontsize=8,
            facecolor="#1a1a1a",
            edgecolor="#333333",
            labelcolor="white",
        )
        legend.get_frame().set_alpha(0.8)

    stats = graph_data["stats"]
    ax.set_title(
        f"Memory Graph \u2014 {stats['total_memories']} notes, {stats['total_links']} links",
        color="white",
        fontsize=14,
        fontweight="bold",
        pad=15,
    )
    ax.axis("off")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0f0f0f")
    plt.close(fig)
    return buf.getvalue()


@router.get(
    "/api/amem/{plan_id}/graph-image",
    responses={404: {"description": "Not found"}},
)
async def get_memory_graph_image(
    plan_id: str, user: Annotated[dict, Depends(get_current_user)] = None
):
    """Render the memory graph as a PNG image."""
    import asyncio
    import io
    from fastapi.responses import StreamingResponse

    mem_dir = _resolve_memory_dir(plan_id)
    notes_dir = mem_dir / "notes"
    notes = _load_notes(notes_dir)
    graph_data = _build_graph(notes)

    if not graph_data["nodes"]:
        raise HTTPException(status_code=404, detail="No memories to graph")

    loop = asyncio.get_event_loop()
    try:
        png_bytes = await loop.run_in_executor(None, _render_graph_png, graph_data)
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    return StreamingResponse(io.BytesIO(png_bytes), media_type="image/png")


@router.get("/api/amem/{plan_id}/notes", responses={404: {"description": "Not found"}})
async def list_memory_notes(
    plan_id: str, user: Annotated[dict, Depends(get_current_user)] = None
) -> list:
    """List all memory notes for a plan's project."""
    mem_dir = _resolve_memory_dir(plan_id)
    notes_dir = mem_dir / "notes"
    notes = _load_notes(notes_dir)
    for n in notes:
        n.pop("content", None)
    return notes


@router.get(
    "/api/amem/{plan_id}/notes/{note_id}", responses={404: {"description": "Not found"}}
)
async def get_memory_note(
    plan_id: str, note_id: str, user: Annotated[dict, Depends(get_current_user)] = None
) -> dict:
    """Get a single memory note by ID."""
    mem_dir = _resolve_memory_dir(plan_id)
    notes_dir = mem_dir / "notes"
    notes = _load_notes(notes_dir)
    for note in notes:
        if note["id"] == note_id:
            return note
    raise HTTPException(status_code=404, detail=f"Note {note_id} not found")


@router.get("/api/amem/{plan_id}/stats", responses={404: {"description": "Not found"}})
async def get_memory_stats(
    plan_id: str, user: Annotated[dict, Depends(get_current_user)] = None
) -> dict:
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
