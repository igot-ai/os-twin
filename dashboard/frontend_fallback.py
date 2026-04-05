from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional


def _first_existing(candidates: Iterable[Path]) -> Optional[Path]:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


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
        path for path in ideas_dir.glob("*.html") if path.stem.startswith("pt-")
    )
    if html_templates:
        return html_templates[0]

    dir_templates = sorted(
        path / "index.html"
        for path in ideas_dir.iterdir()
        if path.is_dir() and path.name.startswith("pt-")
    )
    return _first_existing(dir_templates)


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

    return fe_out_dir / "index.html"
