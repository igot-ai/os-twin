"""Tests for dashboard/plan_agent.py — pure functions only (no LLM calls)."""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from dashboard.plan_agent import (
    parse_structured_response,
    _load_available_roles,
    build_messages,
    get_system_prompt,
    _resolve_model,
    _execute_tool_call,
)
from dashboard.llm_client import ChatMessage, ToolCall


class TestParseStructuredResponse:
    """Tests for parse_structured_response()."""

    def test_full_well_structured_response(self):
        text = (
            "# EXPLANATION\n"
            "I restructured the plan into three epics.\n\n"
            "# ACTIONS\n"
            "- CREATE: dashboard/models.py\n"
            "- UPDATE: PLAN.md\n\n"
            "# PLAN\n"
            "# Plan: My Project\n\n"
            "## Epic: EPIC-001 — Setup\n"
            "Bootstrap the project."
        )
        result = parse_structured_response(text)
        assert result["explanation"] == "I restructured the plan into three epics."
        assert len(result["actions"]) == 2
        assert result["actions"][0] == {"action": "CREATE", "path": "dashboard/models.py"}
        assert result["actions"][1] == {"action": "UPDATE", "path": "PLAN.md"}
        assert "My Project" in result["plan"]
        assert "EPIC-001" in result["plan"]
        assert result["full_response"] == text

    def test_response_with_only_explanation_and_plan(self):
        text = (
            "# EXPLANATION\n"
            "Minor tweaks.\n\n"
            "# PLAN\n"
            "# Plan: Revised\n"
            "Content here."
        )
        result = parse_structured_response(text)
        assert result["explanation"] == "Minor tweaks."
        assert result["actions"] == []
        assert "Revised" in result["plan"]
        assert "Content here." in result["plan"]

    def test_fallback_when_no_sections_but_looks_like_plan(self):
        text = "# Plan\n\n## Epics\n\n### EPIC-001\nDo something."
        result = parse_structured_response(text)
        assert result["actions"] == []
        assert result["plan"] != ""

    def test_empty_text(self):
        result = parse_structured_response("")
        assert result["explanation"] == ""
        assert result["actions"] == []
        assert result["plan"] == ""
        assert result["full_response"] == ""

    def test_multiple_explanation_sections_concatenated(self):
        text = (
            "# EXPLANATION\n"
            "First part.\n\n"
            "# ACTIONS\n"
            "- CREATE: a.py\n\n"
            "# EXPLANATION\n"
            "Second part.\n\n"
            "# PLAN\n"
            "The plan content."
        )
        result = parse_structured_response(text)
        assert "First part." in result["explanation"]
        assert "Second part." in result["explanation"]

    def test_action_format_create(self):
        text = "# ACTIONS\n- CREATE: path/to/file.py\n# PLAN\nDone."
        result = parse_structured_response(text)
        assert len(result["actions"]) == 1
        assert result["actions"][0] == {"action": "CREATE", "path": "path/to/file.py"}

    def test_action_format_update_no_dash(self):
        text = "# ACTIONS\nUPDATE: PLAN.md\n# PLAN\nDone."
        result = parse_structured_response(text)
        assert len(result["actions"]) == 1
        assert result["actions"][0] == {"action": "UPDATE", "path": "PLAN.md"}

    def test_action_format_delete_bracket(self):
        text = "# ACTIONS\n- [DELETE] old_file.py\n# PLAN\nDone."
        result = parse_structured_response(text)
        assert len(result["actions"]) == 1
        assert result["actions"][0]["action"] == "DELETE"
        assert result["actions"][0]["path"] == "old_file.py"

    def test_action_case_insensitive(self):
        text = "# ACTIONS\n- create: foo.py\n# PLAN\nDone."
        result = parse_structured_response(text)
        assert len(result["actions"]) == 1
        assert result["actions"][0]["action"] == "CREATE"

    def test_no_fallback_when_text_has_no_plan_markers(self):
        text = "Hello, this is just a random chat message."
        result = parse_structured_response(text)
        assert result["plan"] == ""
        assert result["explanation"] == ""

    def test_multiline_plan_section(self):
        text = (
            "# PLAN\n"
            "# Plan: Test\n\n"
            "## Epic: EPIC-001 — A\n"
            "Details for A.\n\n"
            "## Epic: EPIC-002 — B\n"
            "Details for B."
        )
        result = parse_structured_response(text)
        assert "EPIC-001" in result["plan"]
        assert "EPIC-002" in result["plan"]


class TestLoadAvailableRoles:
    """Tests for _load_available_roles()."""

    DEFAULT = "Available roles: engineer, qa, architect, or any custom role you define."

    def test_agents_dir_is_none(self):
        assert _load_available_roles(None) == self.DEFAULT

    def test_registry_json_not_exists(self, tmp_path):
        assert _load_available_roles(tmp_path) == self.DEFAULT

    def test_registry_json_with_roles(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        registry = {
            "roles": [
                {"name": "engineer", "description": "Builds stuff", "capabilities": ["code", "test"]},
                {"name": "qa", "description": "Tests stuff"},
            ]
        }
        (roles_dir / "registry.json").write_text(json.dumps(registry))
        result = _load_available_roles(tmp_path)
        assert "engineer" in result
        assert "Builds stuff" in result
        assert "code, test" in result
        assert "qa" in result
        assert "Tests stuff" in result
        assert "custom roles" in result.lower()

    def test_registry_json_empty_roles(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        (roles_dir / "registry.json").write_text(json.dumps({"roles": []}))
        assert _load_available_roles(tmp_path) == self.DEFAULT

    def test_registry_json_malformed(self, tmp_path):
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        (roles_dir / "registry.json").write_text("{{{not json")
        assert _load_available_roles(tmp_path) == self.DEFAULT


class TestResolveModel:
    """Tests for _resolve_model()."""

    def test_provider_model_format(self):
        model, provider = _resolve_model("anthropic:claude-3-opus")
        assert model == "claude-3-opus"
        assert provider == "anthropic"

    def test_provider_model_format_with_slash(self):
        model, provider = _resolve_model("google-vertex/gemini-3-flash")
        assert model == "gemini-3-flash"
        assert provider == "google-vertex"

    def test_bare_model_name_openai(self):
        model, provider = _resolve_model("gpt-4-turbo")
        assert model == "gpt-4-turbo"
        assert provider == "openai"

    def test_bare_model_name_anthropic(self):
        model, provider = _resolve_model("claude-3-sonnet")
        assert model == "claude-3-sonnet"
        assert provider == "anthropic"

    def test_bare_model_name_gemini(self):
        model, provider = _resolve_model("gemini-1.5-pro")
        assert model == "gemini-1.5-pro"
        assert provider == "google"


class TestBuildMessages:
    """Tests for build_messages()."""

    def test_simple_message_only(self):
        msgs = build_messages("Hello", system_prompt="You are helpful.")
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"
        assert msgs[1].content == "Hello"

    def test_with_plan_content(self):
        msgs = build_messages("Improve this", plan_content="# Plan: Foo", system_prompt="System")
        assert len(msgs) == 3
        assert msgs[0].role == "system"
        assert msgs[0].content == "System"
        assert msgs[1].role == "system"
        assert "# Plan: Foo" in msgs[1].content
        assert msgs[2].role == "user"
        assert msgs[2].content == "Improve this"

    def test_empty_plan_content_no_extra_system_message(self):
        msgs = build_messages("Hello", plan_content="   ", system_prompt="System")
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"

    def test_with_chat_history(self):
        history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ]
        msgs = build_messages("Follow-up", chat_history=history, system_prompt="System")
        assert len(msgs) == 4
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"
        assert msgs[1].content == "First question"
        assert msgs[2].role == "assistant"
        assert msgs[2].content == "First answer"
        assert msgs[3].role == "user"
        assert msgs[3].content == "Follow-up"

    def test_with_images_stored_in_chatmessage(self):
        """Images are stored in ChatMessage.images, not embedded in content text."""
        images = [{"url": "https://example.com/img.png"}]
        msgs = build_messages("What's this?", images=images, system_prompt="System")
        assert len(msgs) == 2
        assert msgs[1].role == "user"
        assert msgs[1].content == "What's this?"
        assert "https://example.com/img.png" in msgs[1].images

    def test_with_plan_and_history_and_images(self):
        history = [{"role": "user", "content": "Hi"}]
        images = [{"url": "https://example.com/x.png"}]
        msgs = build_messages(
            "Describe",
            plan_content="# Plan",
            chat_history=history,
            images=images,
            system_prompt="System",
        )
        assert len(msgs) == 4
        assert msgs[0].role == "system"
        assert msgs[1].role == "system"
        assert msgs[2].role == "user"
        assert msgs[3].role == "user"


class TestGetSystemPrompt:
    """Tests for get_system_prompt()."""

    def test_plans_dir_with_template(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        template = plans_dir / "PLAN.template.md"
        template.write_text("My template content with {{AVAILABLE_ROLES}}")

        agents_dir = tmp_path
        prompt = get_system_prompt(plans_dir=plans_dir, agents_dir=agents_dir)
        assert "Plan Architect" in prompt
        assert "My template content" in prompt
        assert "{{AVAILABLE_ROLES}}" not in prompt
        assert "Available roles" in prompt

    def test_plans_dir_without_template(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        agents_dir = tmp_path
        prompt = get_system_prompt(plans_dir=plans_dir, agents_dir=agents_dir)
        assert "Plan Architect" in prompt
        assert "Template not found" in prompt

    def test_no_plans_dir(self):
        prompt = get_system_prompt(plans_dir=None)
        assert "Plan Architect" in prompt
        assert "Plans directory not configured" in prompt

    def test_working_dir_appears_in_prompt(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "PLAN.template.md").write_text("template")
        prompt = get_system_prompt(
            plans_dir=plans_dir,
            agents_dir=tmp_path,
            working_dir="/my/project/dir",
        )
        assert "/my/project/dir" in prompt

    def test_available_roles_placeholder_replaced(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        (plans_dir / "PLAN.template.md").write_text(
            "Roles section: {{AVAILABLE_ROLES}}"
        )
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        registry = {"roles": [{"name": "devops", "description": "Infra work"}]}
        (roles_dir / "registry.json").write_text(json.dumps(registry))

        prompt = get_system_prompt(plans_dir=plans_dir, agents_dir=tmp_path)
        assert "devops" in prompt
        assert "{{AVAILABLE_ROLES}}" not in prompt


class TestExecuteToolCall:
    """Tests for _execute_tool_call()."""

    def test_read_existing_plan_success(self, tmp_path):
        (tmp_path / "my-plan.md").write_text("# Plan: My Plan\n\n## EPIC-001")
        tc = ToolCall(id="tc1", name="read_existing_plan", arguments={"plan_id": "my-plan"})
        result = _execute_tool_call(tc, tmp_path)
        assert "EPIC-001" in result

    def test_read_existing_plan_not_found(self, tmp_path):
        tc = ToolCall(id="tc2", name="read_existing_plan", arguments={"plan_id": "missing"})
        result = _execute_tool_call(tc, tmp_path)
        assert result.startswith("Error: Plan 'missing' not found.")

    def test_read_existing_plan_no_plans_dir(self):
        tc = ToolCall(id="tc3", name="read_existing_plan", arguments={"plan_id": "x"})
        result = _execute_tool_call(tc, None)
        assert result == "Error: Plans directory not configured."

    def test_unknown_tool_returns_error(self, tmp_path):
        tc = ToolCall(id="tc4", name="nonexistent_tool", arguments={})
        result = _execute_tool_call(tc, tmp_path)
        assert "Unknown tool" in result
        assert "nonexistent_tool" in result

    def test_read_existing_plan_empty_plan_id(self, tmp_path):
        """Missing plan_id argument should report plan not found."""
        tc = ToolCall(id="tc5", name="read_existing_plan", arguments={})
        result = _execute_tool_call(tc, tmp_path)
        # plan_id defaults to "" which produces a path that won't exist
        assert "Error:" in result
