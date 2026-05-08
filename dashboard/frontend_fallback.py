from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional


def _first_existing(candidates: Iterable[Path]) -> Optional[Path]:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Dynamic-route template directory mapping
# ---------------------------------------------------------------------------
# Next.js 16 (Turbopack) static export (`output: 'export'`) produces TWO
# kinds of artefacts per dynamic route:
#
#   1. ``{slug}.html``   — the pre-rendered HTML page
#   2. ``{slug}/``       — a directory of RSC payload ``.txt`` files
#      (``__next._tree.txt``, ``__next._head.txt``, ``__next.*.txt``, …)
#
# For routes with ``generateStaticParams``, only the placeholder slug(s)
# exist on disk (e.g. ``knowledge/_``, ``plans/plan-001``, ``ideas/template``).
# When the browser navigates to an *unknown* slug such as
# ``/knowledge/vnexpress_global_news``, the catch-all serves the template
# ``.html`` correctly — but Next.js client subsequently fetches RSC
# payloads from ``/knowledge/vnexpress_global_news/__next.*.txt``, which
# don't exist on disk and currently fall through to ``index.html``, breaking
# client-side hydration of the detail view.
#
# ``_DYNAMIC_ROUTE_TEMPLATES`` maps each section to a callable that resolves
# the canonical template *directory* for that section's dynamic slug.
# ``resolve_frontend_file`` uses this map to redirect RSC ``.txt`` requests
# for unknown slugs into the correct template directory.
# ---------------------------------------------------------------------------


def _find_plan_template_dir(fe_out_dir: Path) -> Optional[Path]:
    """Return the canonical template directory for /plans/[id]."""
    plans_dir = fe_out_dir / "plans"
    if not plans_dir.is_dir():
        return None
    # plan-001 is the default from generateStaticParams
    candidate = plans_dir / "plan-001"
    if candidate.is_dir():
        return candidate
    # Fallback: first plan-* directory
    for p in sorted(plans_dir.iterdir()):
        if p.is_dir() and p.name.startswith("plan-"):
            return p
    return None


def _find_knowledge_template_dir(fe_out_dir: Path) -> Optional[Path]:
    """Return the canonical template directory for /knowledge/[name]."""
    knowledge_dir = fe_out_dir / "knowledge"
    if not knowledge_dir.is_dir():
        return None
    candidate = knowledge_dir / "_"
    if candidate.is_dir():
        return candidate
    # Fallback: first non-_next directory
    for p in sorted(knowledge_dir.iterdir()):
        if p.is_dir() and p.name != "_next":
            return p
    return None


def _find_ideas_template_dir(fe_out_dir: Path) -> Optional[Path]:
    """Return the canonical template directory for /ideas/[threadId]."""
    ideas_dir = fe_out_dir / "ideas"
    if not ideas_dir.is_dir():
        return None
    candidate = ideas_dir / "template"
    if candidate.is_dir():
        return candidate
    for p in sorted(ideas_dir.iterdir()):
        if p.is_dir() and p.name.startswith("pt-"):
            return p
    return None


def _find_epic_template_dir(fe_out_dir: Path) -> Optional[Path]:
    """Return the canonical template directory for /plans/[id]/epics/[ref]."""
    plans_dir = fe_out_dir / "plans"
    if not plans_dir.is_dir():
        return None
    epic = plans_dir / "plan-001" / "epics" / "EPIC-001"
    if epic.is_dir():
        return epic
    for plan_dir in sorted(p for p in plans_dir.iterdir() if p.is_dir()):
        epics = plan_dir / "epics"
        if not epics.is_dir():
            continue
        for e in sorted(epics.iterdir()):
            if e.is_dir() and e.name.startswith("EPIC-"):
                return e
    return None


# ---------------------------------------------------------------------------
# HTML template resolvers (for the initial page request)
# ---------------------------------------------------------------------------

def _resolve_plan_template(fe_out_dir: Path) -> Optional[Path]:
    plans_dir = fe_out_dir / "plans"
    if not plans_dir.is_dir():
        return None

    explicit = _first_existing(
        [
            plans_dir / "plan-001.html",
            plans_dir / "plan-001" / "index.html",
        ]
    )
    if explicit:
        return explicit

    html_templates = sorted(
        path for path in plans_dir.glob("*.html") if path.stem.startswith("plan-")
    )
    if html_templates:
        return html_templates[0]

    dir_templates = sorted(
        path / "index.html"
        for path in plans_dir.iterdir()
        if path.is_dir() and path.name.startswith("plan-")
    )
    return _first_existing(dir_templates)


def _resolve_epic_template(fe_out_dir: Path) -> Optional[Path]:
    plans_dir = fe_out_dir / "plans"
    if not plans_dir.is_dir():
        return None

    explicit = _first_existing(
        [
            plans_dir / "plan-001" / "epics" / "EPIC-001.html",
            plans_dir / "plan-001" / "epics" / "EPIC-001" / "index.html",
        ]
    )
    if explicit:
        return explicit

    for plan_dir in sorted(path for path in plans_dir.iterdir() if path.is_dir()):
        epic_dir = plan_dir / "epics"
        if not epic_dir.is_dir():
            continue

        html_templates = sorted(
            path for path in epic_dir.glob("*.html") if path.stem.startswith("EPIC-")
        )
        if html_templates:
            return html_templates[0]

        dir_templates = sorted(
            path / "index.html"
            for path in epic_dir.iterdir()
            if path.is_dir() and path.name.startswith("EPIC-")
        )
        nested = _first_existing(dir_templates)
        if nested:
            return nested

    return None


def _resolve_ideas_template(fe_out_dir: Path) -> Optional[Path]:
    ideas_dir = fe_out_dir / "ideas"
    if not ideas_dir.is_dir():
        return None

    explicit = _first_existing(
        [
            ideas_dir / "pt-001.html",
            ideas_dir / "pt-001" / "index.html",
        ]
    )
    if explicit:
        return explicit

    html_templates = sorted(
        path for path in ideas_dir.glob("*.html") if path.stem.startswith("pt-") or path.stem == "template"
    )
    if html_templates:
        return html_templates[0]

    dir_templates = sorted(
        path / "index.html"
        for path in ideas_dir.iterdir()
        if path.is_dir() and path.name.startswith("pt-")
    )
    return _first_existing(dir_templates)


def _resolve_knowledge_template(fe_out_dir: Path) -> Optional[Path]:
    """Resolve the pre-rendered template for /knowledge/[name] routes.

    Next.js ``output: 'export'`` with ``generateStaticParams`` returning
    ``[{ name: '_' }]`` produces ``knowledge/_.html`` (or
    ``knowledge/_/index.html``).  Any dynamic namespace slug (e.g.
    ``vnexpress_global_news``) should be served by this template — the
    actual namespace is resolved client-side via ``useParams()``.
    """
    knowledge_dir = fe_out_dir / "knowledge"
    if not knowledge_dir.is_dir():
        return None

    # Preferred: the placeholder produced by generateStaticParams
    explicit = _first_existing(
        [
            knowledge_dir / "_.html",
            knowledge_dir / "_" / "index.html",
        ]
    )
    if explicit:
        return explicit

    # Fallback: any HTML template inside the knowledge directory
    html_templates = sorted(
        path for path in knowledge_dir.glob("*.html")
        if path.stem not in ("index",)
    )
    if html_templates:
        return html_templates[0]

    dir_templates = sorted(
        path / "index.html"
        for path in knowledge_dir.iterdir()
        if path.is_dir() and path.name != "_next"
    )
    return _first_existing(dir_templates)


# ---------------------------------------------------------------------------
# RSC payload resolution for dynamic routes
# ---------------------------------------------------------------------------

def _resolve_dynamic_rsc(fe_out_dir: Path, parts: list[str]) -> Optional[Path]:
    """Resolve Next.js RSC ``.txt`` payload files for dynamic route slugs.

    Next.js 16 (Turbopack) static export stores RSC payloads as ``.txt``
    files in a directory named after the pre-rendered slug.  For example::

        out/knowledge/_/__next._tree.txt        # template slug is "_"
        out/plans/plan-001/__next._tree.txt     # template slug is "plan-001"
        out/ideas/template/__next._tree.txt     # template slug is "template"

    When the browser visits ``/knowledge/vnexpress_global_news``, the Next.js
    client fetches RSC files from ``/knowledge/vnexpress_global_news/__next.*.txt``.
    Those paths don't exist on disk.  This function detects the pattern and
    resolves the request into the canonical template directory.

    Supported patterns:
        - ``knowledge/{slug}/__next.*.txt``           → ``knowledge/_/…``
        - ``plans/{slug}/__next.*.txt``               → ``plans/plan-001/…``
        - ``ideas/{slug}/__next.*.txt``               → ``ideas/template/…``
        - ``plans/{slug}/epics/{ref}/__next.*.txt``   → ``plans/plan-001/epics/EPIC-001/…``
        - ``{slug}.txt``  (RSC root payload next to the HTML, e.g. ``knowledge/vnexpress_global_news.txt``)
    """
    # --- Pattern: {section}/{slug}/__next.*.txt  (3 parts) ---
    if len(parts) == 3 and parts[2].startswith("__next.") and parts[2].endswith(".txt"):
        section, _slug, rsc_file = parts
        template_dir = _get_template_dir(fe_out_dir, section)
        if template_dir:
            candidate = template_dir / rsc_file
            if candidate.is_file():
                return candidate

    # --- Pattern: {section}/{slug}.txt  (RSC root payload, 2 parts with .txt) ---
    if len(parts) == 2 and parts[1].endswith(".txt") and not parts[1].startswith("__next."):
        section = parts[0]
        template_dir = _get_template_dir(fe_out_dir, section)
        if template_dir:
            # The .txt root payload uses the template slug name
            # e.g. knowledge/_.txt for knowledge/[name]
            rsc_root = template_dir.name + ".txt"
            candidate = template_dir.parent / rsc_root
            if candidate.is_file():
                return candidate

    # --- Pattern: plans/{slug}/epics/{ref}/__next.*.txt  (5 parts) ---
    if (
        len(parts) == 5
        and parts[0] == "plans"
        and parts[2] == "epics"
        and parts[4].startswith("__next.")
        and parts[4].endswith(".txt")
    ):
        template_dir = _find_epic_template_dir(fe_out_dir)
        if template_dir:
            candidate = template_dir / parts[4]
            if candidate.is_file():
                return candidate

    return None


def _get_template_dir(fe_out_dir: Path, section: str) -> Optional[Path]:
    """Return the canonical template directory for a given section."""
    resolvers = {
        "plans": _find_plan_template_dir,
        "knowledge": _find_knowledge_template_dir,
        "ideas": _find_ideas_template_dir,
    }
    resolver = resolvers.get(section)
    if resolver:
        return resolver(fe_out_dir)
    return None


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------

def resolve_frontend_file(fe_out_dir: Path, path: str) -> Path:
    normalized = path.strip("/")
    if not normalized:
        return fe_out_dir / "index.html"

    exact = fe_out_dir / normalized
    if exact.is_file():
        return exact

    html_file = fe_out_dir / f"{normalized}.html"
    if html_file.is_file():
        return html_file

    index_file = fe_out_dir / normalized / "index.html"
    if index_file.is_file():
        return index_file

    parts = normalized.split("/")

    # --- RSC payload resolution for dynamic routes ---
    # Must run BEFORE HTML template resolution because RSC files are
    # deeper paths (3+ segments) that would otherwise fall through
    # to index.html.
    rsc_resolved = _resolve_dynamic_rsc(fe_out_dir, parts)
    if rsc_resolved:
        return rsc_resolved

    # --- HTML template resolution for dynamic routes ---
    if len(parts) == 4 and parts[0] == "plans" and parts[2] == "epics":
        epic_template = _resolve_epic_template(fe_out_dir)
        if epic_template:
            return epic_template

    if len(parts) == 2 and parts[0] == "ideas":
        ideas_template = _resolve_ideas_template(fe_out_dir)
        if ideas_template:
            return ideas_template

    if len(parts) == 2 and parts[0] == "plans":
        plan_template = _resolve_plan_template(fe_out_dir)
        if plan_template:
            return plan_template

    if len(parts) == 2 and parts[0] == "knowledge":
        knowledge_template = _resolve_knowledge_template(fe_out_dir)
        if knowledge_template:
            return knowledge_template

    return fe_out_dir / "index.html"
