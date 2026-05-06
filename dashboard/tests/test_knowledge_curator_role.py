"""Tests for the knowledge-curator agent role (EPIC-006).

Validates:
1. Role definition files exist and are well-formed
2. Skills are properly structured
3. Confirmation gate works correctly for destructive operations
4. Role is registered in the registry
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def role_dir() -> Path:
    """Path to the knowledge-curator role directory."""
    # Path from dashboard/tests to agent-os/contributes/roles/knowledge-curator
    # test file: agent-os/dashboard/tests/test_knowledge_curator_role.py
    # role: agent-os/contributes/roles/knowledge-curator/
    return Path(__file__).resolve().parent.parent.parent / "contributes" / "roles" / "knowledge-curator"


@pytest.fixture
def skills_dir() -> Path:
    """Path to the knowledge-curator skills directory."""
    # Skills are in agent-os/.agents/skills/roles/knowledge-curator
    return Path(__file__).resolve().parent.parent.parent / ".agents" / "skills" / "roles" / "knowledge-curator"


@pytest.fixture
def registry_path() -> Path:
    """Path to the roles registry."""
    # Registry is in agent-os/.agents/roles/registry.json
    return Path(__file__).resolve().parent.parent.parent / ".agents" / "roles" / "registry.json"


@pytest.fixture
def mcp_server_path() -> Path:
    """Path to the knowledge MCP server."""
    # MCP server is in dashboard/knowledge/mcp_server.py
    return Path(__file__).resolve().parent.parent / "knowledge" / "mcp_server.py"


# ---------------------------------------------------------------------------
# Role Definition Tests (TASK-E-001, TASK-E-002)
# ---------------------------------------------------------------------------


def test_role_json_exists(role_dir: Path) -> None:
    """role.json file must exist."""
    role_json = role_dir / "role.json"
    assert role_json.exists(), f"role.json not found at {role_json}"


def test_role_json_valid_json(role_dir: Path) -> None:
    """role.json must be valid JSON."""
    role_json = role_dir / "role.json"
    content = role_json.read_text()
    data = json.loads(content)
    assert isinstance(data, dict), "role.json must contain a JSON object"


def test_role_json_required_fields(role_dir: Path) -> None:
    """role.json must have all required fields."""
    role_json = role_dir / "role.json"
    data = json.loads(role_json.read_text())
    
    required_fields = ["name", "description", "capabilities", "prompt_file", "model"]
    for field in required_fields:
        assert field in data, f"role.json missing required field: {field}"
    
    assert data["name"] == "knowledge-curator", f"Expected name 'knowledge-curator', got {data['name']}"


def test_role_json_model_format(role_dir: Path) -> None:
    """role.json model must be provider-prefixed."""
    role_json = role_dir / "role.json"
    data = json.loads(role_json.read_text())
    
    model = data.get("model", "")
    assert "/" in model, f"Model must be provider-prefixed (e.g., google-vertex/gemini-3-flash-preview), got: {model}"


def test_role_md_exists(role_dir: Path) -> None:
    """ROLE.md file must exist."""
    role_md = role_dir / "ROLE.md"
    assert role_md.exists(), f"ROLE.md not found at {role_md}"


def test_role_md_has_frontmatter(role_dir: Path) -> None:
    """ROLE.md must have YAML frontmatter with name."""
    role_md = role_dir / "ROLE.md"
    content = role_md.read_text()
    
    assert content.startswith("---"), "ROLE.md must start with YAML frontmatter"
    assert "name: knowledge-curator" in content, "ROLE.md frontmatter must contain name: knowledge-curator"


def test_role_md_has_sections(role_dir: Path) -> None:
    """ROLE.md must have required documentation sections."""
    role_md = role_dir / "ROLE.md"
    content = role_md.read_text()
    
    required_sections = [
        "## Your Responsibilities",
        "## Your Tool Inventory",
        "## Confirmation Gate",
        "## Output Artifacts",
    ]
    
    for section in required_sections:
        assert section in content, f"ROLE.md missing required section: {section}"


# ---------------------------------------------------------------------------
# Skills Tests (TASK-E-003)
# ---------------------------------------------------------------------------


def test_skills_directory_exists(skills_dir: Path) -> None:
    """Skills directory for knowledge-curator must exist."""
    assert skills_dir.exists(), f"Skills directory not found at {skills_dir}"








# ---------------------------------------------------------------------------
# Registry Tests (TASK-E-005)
# ---------------------------------------------------------------------------


def test_role_registered_in_registry(registry_path: Path) -> None:
    """knowledge-curator must be registered in the roles registry."""
    assert registry_path.exists(), f"Registry not found at {registry_path}"
    
    data = json.loads(registry_path.read_text())
    roles = data.get("roles", [])
    
    role_names = [r.get("name") for r in roles]
    assert "knowledge-curator" in role_names, "knowledge-curator not found in registry roles"


def test_role_registry_entry_complete(registry_path: Path) -> None:
    """Registry entry for knowledge-curator must have all required fields."""
    data = json.loads(registry_path.read_text())
    roles = data.get("roles", [])
    
    curator_entry = next((r for r in roles if r.get("name") == "knowledge-curator"), None)
    assert curator_entry is not None, "knowledge-curator entry not found"
    
    required_fields = ["name", "description", "definition", "prompt", "capabilities"]
    for field in required_fields:
        assert field in curator_entry, f"Registry entry missing field: {field}"


def test_skills_registered_in_registry(registry_path: Path) -> None:
    """All knowledge-curator skills must be registered in the registry."""
    data = json.loads(registry_path.read_text())
    skills = data.get("skills", {}).get("available", [])
    
    skill_names = [s.get("name") for s in skills]
    required_skills = [
        "curate-namespace",
        "set-retention",
        "schedule-refresh",
        "audit-quality",
        "propose-rebuild",
    ]
    
    for skill_name in required_skills:
        assert skill_name in skill_names, f"Skill '{skill_name}' not found in registry"


# ---------------------------------------------------------------------------
# Confirmation Gate Tests (TASK-E-004)
# ---------------------------------------------------------------------------


def test_confirmation_gate_functions_exist(mcp_server_path: Path) -> None:
    """MCP server must have confirmation gate helper functions."""
    content = mcp_server_path.read_text()
    
    assert "_get_mcp_actor" in content, "Missing _get_mcp_actor function"
    assert "_requires_confirmation" in content, "Missing _requires_confirmation function"


def test_delete_namespace_has_confirm_param(mcp_server_path: Path) -> None:
    """knowledge_delete_namespace must have confirm parameter."""
    content = mcp_server_path.read_text()
    
    # Check function signature includes confirm parameter
    assert "def knowledge_delete_namespace" in content, "Missing knowledge_delete_namespace function"
    assert "confirm: bool" in content or "confirm=" in content, \
        "knowledge_delete_namespace missing confirm parameter"




def test_confirmation_gate_rejection_message(mcp_server_path: Path) -> None:
    """Confirmation gate must return CONFIRMATION_REQUIRED error code."""
    content = mcp_server_path.read_text()
    
    assert "CONFIRMATION_REQUIRED" in content, \
        "Confirmation gate must return CONFIRMATION_REQUIRED error code"


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


def test_confirmation_gate_delete_rejects_without_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Delete without confirm must be rejected when OSTWIN_MCP_ACTOR=knowledge-curator."""
    # Set the actor to knowledge-curator
    monkeypatch.setenv("OSTWIN_MCP_ACTOR", "knowledge-curator")
    
    # Import after setting env var
    from dashboard.knowledge.mcp_server import knowledge_delete_namespace
    
    # Call without confirm should be rejected
    result = knowledge_delete_namespace("test-namespace")
    
    assert "error" in result, "Expected error in result"
    assert result.get("code") == "CONFIRMATION_REQUIRED", \
        f"Expected CONFIRMATION_REQUIRED, got {result.get('code')}"


def test_confirmation_gate_delete_allows_with_confirm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Delete with confirm=True must be allowed for knowledge-curator."""
    # Set up isolated knowledge directory
    monkeypatch.setenv("OSTWIN_KNOWLEDGE_DIR", str(tmp_path))
    monkeypatch.setenv("OSTWIN_MCP_ACTOR", "knowledge-curator")
    
    # Reset service singleton
    import dashboard.knowledge.mcp_server as mcp_mod
    mcp_mod._service = None
    
    try:
        from dashboard.knowledge.mcp_server import (
            knowledge_create_namespace,
            knowledge_delete_namespace,
        )
        
        # Create a test namespace
        create_result = knowledge_create_namespace("test-confirm-delete")
        assert "error" not in create_result, f"Failed to create namespace: {create_result}"
        
        # Delete with confirm=True should succeed
        delete_result = knowledge_delete_namespace("test-confirm-delete", confirm=True)
        assert "deleted" in delete_result, f"Expected 'deleted' in result, got: {delete_result}"
        assert delete_result.get("deleted") is True, "Expected deleted=True"
    finally:
        mcp_mod._service = None


def test_confirmation_gate_not_required_for_other_actors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Delete must work without confirm for non-curator actors."""
    # Set a different actor
    monkeypatch.setenv("OSTWIN_MCP_ACTOR", "engineer")
    monkeypatch.setenv("OSTWIN_KNOWLEDGE_DIR", str(tmp_path := Path("/tmp/test-knowledge-curator-other")))
    tmp_path.mkdir(parents=True, exist_ok=True)
    
    # Reset service singleton
    import dashboard.knowledge.mcp_server as mcp_mod
    mcp_mod._service = None
    
    try:
        from dashboard.knowledge.mcp_server import (
            knowledge_create_namespace,
            knowledge_delete_namespace,
        )
        
        # Create a test namespace
        create_result = knowledge_create_namespace("test-non-curator")
        assert "error" not in create_result, f"Failed to create namespace: {create_result}"
        
        # Delete without confirm should work for non-curator
        delete_result = knowledge_delete_namespace("test-non-curator", confirm=False)
        assert "deleted" in delete_result, f"Expected 'deleted' in result, got: {delete_result}"
    finally:
        mcp_mod._service = None




# ---------------------------------------------------------------------------
# Acceptance Criteria Tests (from EPIC-006 brief)
# ---------------------------------------------------------------------------


def test_ac_role_json_name() -> None:
    """AC: cat role.json | jq .name returns 'knowledge-curator'."""
    role_json = Path(__file__).resolve().parent.parent.parent / "contributes" / "roles" / "knowledge-curator" / "role.json"
    data = json.loads(role_json.read_text())
    assert data.get("name") == "knowledge-curator"


def test_ac_role_has_allowed_mcp_tools() -> None:
    """AC: Role must define allowed MCP tools."""
    role_json = Path(__file__).resolve().parent.parent.parent / "contributes" / "roles" / "knowledge-curator" / "role.json"
    data = json.loads(role_json.read_text())
    
    # Check that knowledge tools are in allowed list
    allowed_tools = data.get("allowed_mcp_tools", [])
    assert "knowledge_list_namespaces" in allowed_tools, "Missing knowledge_list_namespaces in allowed tools"
    assert "knowledge_delete_namespace" in allowed_tools, "Missing knowledge_delete_namespace in allowed tools"


def test_ac_role_has_restricted_tools() -> None:
    """AC: Curator must NOT have bash/write tools."""
    role_json = Path(__file__).resolve().parent.parent.parent / "contributes" / "roles" / "knowledge-curator" / "role.json"
    data = json.loads(role_json.read_text())
    
    restricted = data.get("restricted_tools", [])
    assert "bash" in restricted, "bash should be restricted for curator"
    assert "write" in restricted, "write should be restricted for curator"
