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


# ---------------------------------------------------------------------------
# RSC payload resolution tests (Next.js 16 Turbopack static export)
# ---------------------------------------------------------------------------


def test_knowledge_rsc_tree_resolves_to_template_dir(tmp_path: Path) -> None:
    """RSC __next._tree.txt for unknown knowledge slug -> template dir."""
    _write(tmp_path / "index.html")
    _write(tmp_path / "knowledge" / "_.html")
    _write(tmp_path / "knowledge" / "_" / "__next._tree.txt", "rsc-tree")

    resolved = resolve_frontend_file(
        tmp_path, "knowledge/vnexpress_global_news/__next._tree.txt"
    )
    assert resolved == tmp_path / "knowledge" / "_" / "__next._tree.txt"


def test_knowledge_rsc_page_payload_resolves(tmp_path: Path) -> None:
    """RSC page-level payload for unknown knowledge slug -> template dir."""
    _write(tmp_path / "index.html")
    _write(tmp_path / "knowledge" / "_.html")
    _write(
        tmp_path / "knowledge" / "_" / "__next.knowledge.$d$name.__PAGE__.txt",
        "rsc-page",
    )

    resolved = resolve_frontend_file(
        tmp_path,
        "knowledge/vnexpress_global_news/__next.knowledge.$d$name.__PAGE__.txt",
    )
    assert (
        resolved
        == tmp_path / "knowledge" / "_" / "__next.knowledge.$d$name.__PAGE__.txt"
    )


def test_plans_rsc_tree_resolves_to_template_dir(tmp_path: Path) -> None:
    """RSC __next._tree.txt for unknown plan slug -> template dir."""
    _write(tmp_path / "index.html")
    _write(tmp_path / "plans" / "plan-001.html")
    _write(tmp_path / "plans" / "plan-001" / "__next._tree.txt", "rsc-tree")

    resolved = resolve_frontend_file(
        tmp_path, "plans/my-custom-plan/__next._tree.txt"
    )
    assert resolved == tmp_path / "plans" / "plan-001" / "__next._tree.txt"


def test_ideas_rsc_tree_resolves_to_template_dir(tmp_path: Path) -> None:
    """RSC __next._tree.txt for unknown ideas slug -> template dir."""
    _write(tmp_path / "index.html")
    _write(tmp_path / "ideas" / "template.html")
    _write(tmp_path / "ideas" / "template" / "__next._tree.txt", "rsc-tree")

    resolved = resolve_frontend_file(
        tmp_path, "ideas/some-thread-id/__next._tree.txt"
    )
    assert resolved == tmp_path / "ideas" / "template" / "__next._tree.txt"


def test_epics_rsc_tree_resolves_to_template_dir(tmp_path: Path) -> None:
    """RSC __next._tree.txt for unknown epic slug -> template dir."""
    _write(tmp_path / "index.html")
    _write(
        tmp_path / "plans" / "plan-001" / "epics" / "EPIC-001" / "__next._tree.txt",
        "rsc-tree",
    )

    resolved = resolve_frontend_file(
        tmp_path,
        "plans/my-plan/epics/EPIC-999/__next._tree.txt",
    )
    assert (
        resolved
        == tmp_path / "plans" / "plan-001" / "epics" / "EPIC-001" / "__next._tree.txt"
    )


def test_static_rsc_files_resolve_directly(tmp_path: Path) -> None:
    """RSC files for static (non-dynamic) routes should resolve directly."""
    _write(tmp_path / "index.html")
    _write(tmp_path / "knowledge" / "__next._tree.txt", "static-rsc")

    resolved = resolve_frontend_file(tmp_path, "knowledge/__next._tree.txt")
    assert resolved == tmp_path / "knowledge" / "__next._tree.txt"


def test_knowledge_html_still_resolves_correctly(tmp_path: Path) -> None:
    """HTML resolution for unknown knowledge slug should still work."""
    _write(tmp_path / "index.html")
    _write(tmp_path / "knowledge" / "_.html", "template")
    _write(tmp_path / "knowledge" / "_" / "__next._tree.txt", "rsc-tree")

    resolved = resolve_frontend_file(tmp_path, "knowledge/any-namespace")
    assert resolved == tmp_path / "knowledge" / "_.html"

