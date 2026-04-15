"""
test_parse_roles_markdown.py — Unit tests for _parse_roles_from_markdown().

Mirrors the role-parsing test matrix from PlanParser.Tests.ps1 to ensure
the Python backend stays aligned with the canonical PowerShell parser.
"""

import pytest
from dashboard.routes.plans import _parse_roles_from_markdown


# ─── Backward compatibility: plain format (no @) ─────────────────────

class TestPlainRolesFormat:
    """Existing Roles: engineer, qa format must keep working."""

    def test_comma_separated_roles(self):
        md = "Roles: engineer, qa"
        assert _parse_roles_from_markdown(md) == ["engineer", "qa"]

    def test_singular_role_directive(self):
        md = "Role: engineer"
        assert _parse_roles_from_markdown(md) == ["engineer"]

    def test_single_role(self):
        md = "Roles: designer"
        assert _parse_roles_from_markdown(md) == ["designer"]

    def test_roles_with_instance_suffix(self):
        md = "Roles: engineer:be, engineer:fe"
        assert _parse_roles_from_markdown(md) == ["engineer:be", "engineer:fe"]

    def test_strips_trailing_comments(self):
        md = "Roles: engineer, qa (primary roles)"
        assert _parse_roles_from_markdown(md) == ["engineer", "qa"]

    def test_ignores_placeholder_angles(self):
        md = "Roles: <role-name>"
        assert _parse_roles_from_markdown(md) == []

    def test_empty_text(self):
        assert _parse_roles_from_markdown("") == []

    def test_no_roles_directive(self):
        md = "# Plan\n\nSome text without any roles."
        assert _parse_roles_from_markdown(md) == []

    def test_deduplicates_preserving_order(self):
        md = "Roles: engineer, qa, engineer"
        assert _parse_roles_from_markdown(md) == ["engineer", "qa"]


# ─── @-prefixed format ───────────────────────────────────────────────

class TestAtPrefixedRoles:
    """Roles: @engineer, @qa format — strips @ for lifecycle compatibility."""

    def test_at_prefixed_roles(self):
        md = "Roles: @engineer, @qa"
        result = _parse_roles_from_markdown(md)
        assert result == ["engineer", "qa"]
        assert "@engineer" not in result
        assert "@qa" not in result

    def test_mixed_at_and_plain(self):
        md = "Roles: @engineer, qa, @designer"
        assert _parse_roles_from_markdown(md) == ["engineer", "qa", "designer"]

    def test_space_separated_at_roles(self):
        md = "Roles: @engineer @qa @designer"
        assert _parse_roles_from_markdown(md) == ["engineer", "qa", "designer"]

    def test_at_roles_with_instance_suffix(self):
        md = "Roles: @engineer:fe, @qa"
        assert _parse_roles_from_markdown(md) == ["engineer:fe", "qa"]

    def test_trailing_ellipsis_ignored(self):
        md = "Roles: @qa, ..."
        result = _parse_roles_from_markdown(md)
        assert result == ["qa"]
        assert "..." not in result

    def test_at_roles_deduplicated(self):
        md = "Roles: @engineer, @qa, @engineer"
        assert _parse_roles_from_markdown(md) == ["engineer", "qa"]


# ─── Markdown formatting variants ────────────────────────────────────

class TestMarkdownFormatVariants:
    """Heading, bold, and italic wrapping around Roles: directive."""

    def test_heading_h3_format(self):
        md = "### Roles: @engineer, @qa"
        assert _parse_roles_from_markdown(md) == ["engineer", "qa"]

    def test_heading_h2_format(self):
        md = "## Roles: engineer, qa"
        assert _parse_roles_from_markdown(md) == ["engineer", "qa"]

    def test_heading_h4_format(self):
        md = "#### Roles: @designer"
        assert _parse_roles_from_markdown(md) == ["designer"]

    def test_bold_format(self):
        md = "**Roles**: @designer"
        assert _parse_roles_from_markdown(md) == ["designer"]

    def test_italic_format(self):
        md = "*Role*: @architect"
        assert _parse_roles_from_markdown(md) == ["architect"]

    def test_bold_singular(self):
        md = "**Role**: engineer"
        assert _parse_roles_from_markdown(md) == ["engineer"]


# ─── Multi-epic plan parsing ─────────────────────────────────────────

class TestMultiEpicParsing:
    """Roles: directives from different epics in the same markdown."""

    def test_multiple_role_lines(self):
        md = (
            "## EPIC-001 — Auth\n"
            "Roles: @engineer, @qa\n"
            "\n"
            "## EPIC-002 — Frontend\n"
            "Roles: @designer, @engineer\n"
        )
        # Should collect all unique roles from all directives
        assert _parse_roles_from_markdown(md) == ["engineer", "qa", "designer"]

    def test_mixed_formats_across_epics(self):
        md = (
            "## EPIC-001\n"
            "### Roles: @engineer:be\n"
            "\n"
            "## EPIC-002\n"
            "Roles: engineer:fe\n"
        )
        assert _parse_roles_from_markdown(md) == ["engineer:be", "engineer:fe"]


# ─── Edge cases ──────────────────────────────────────────────────────

class TestEdgeCases:
    """Unusual but valid inputs."""

    def test_roles_mid_document(self):
        md = (
            "# Plan: Test\n"
            "\n"
            "Some description text.\n"
            "\n"
            "## EPIC-001 — Setup\n"
            "Objective: Do things\n"
            "Roles: @engineer, @qa\n"
            "Working_dir: src/\n"
        )
        assert _parse_roles_from_markdown(md) == ["engineer", "qa"]

    def test_does_not_match_inline_roles(self):
        # "Roles:" must be at start of line (possibly after heading/bold)
        md = "The Roles: engineer, qa are defined."
        # "The Roles:" won't match because "The " prefix isn't heading/bold
        assert _parse_roles_from_markdown(md) == []

    def test_whitespace_around_names(self):
        md = "Roles:   @engineer ,  @qa  , @designer  "
        assert _parse_roles_from_markdown(md) == ["engineer", "qa", "designer"]

    def test_comma_and_space_mixed_separators(self):
        md = "Roles: @engineer, @qa @designer"
        assert _parse_roles_from_markdown(md) == ["engineer", "qa", "designer"]
