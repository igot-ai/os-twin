from pathlib import Path

from dashboard.frontend_fallback import resolve_frontend_file


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_exact_new_plan_route_stays_on_create_page(tmp_path: Path) -> None:
    _write(tmp_path / "index.html")
    _write(tmp_path / "plans" / "new.html", "create")
    _write(tmp_path / "plans" / "plan-001.html", "detail")

    resolved = resolve_frontend_file(tmp_path, "plans/new")

    assert resolved == tmp_path / "plans" / "new.html"


def test_unknown_plan_route_uses_plan_template_not_create_page(tmp_path: Path) -> None:
    _write(tmp_path / "index.html")
    _write(tmp_path / "plans" / "new.html", "create")
    _write(tmp_path / "plans" / "plan-001.html", "detail")

    resolved = resolve_frontend_file(tmp_path, "plans/unified-ai-architect-thread")

    assert resolved == tmp_path / "plans" / "plan-001.html"


def test_unknown_epic_route_uses_epic_template(tmp_path: Path) -> None:
    _write(tmp_path / "index.html")
    _write(tmp_path / "plans" / "new.html", "create")
    _write(tmp_path / "plans" / "plan-001" / "epics" / "EPIC-001.html", "epic-detail")

    resolved = resolve_frontend_file(
        tmp_path,
        "plans/unified-ai-architect-thread/epics/EPIC-009",
    )

    assert resolved == tmp_path / "plans" / "plan-001" / "epics" / "EPIC-001.html"
