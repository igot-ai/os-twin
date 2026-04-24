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
    detect_model,
    build_messages,
    get_system_prompt,
    _resolve_model,
    _execute_tool_call,
    _get_api_key,
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


class TestDetectModel:
    """Tests for detect_model()."""

    def test_google_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-google-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        model, provider = detect_model()
        assert "gemini" in model.lower()
        assert provider == "google"

    def test_anthropic_api_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        model, provider = detect_model()
        assert "claude" in model.lower()
        assert provider == "anthropic"

    def test_openai_api_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
        model, provider = detect_model()
        assert model == "gpt-4o"
        assert provider == "openai"

    def test_no_key_raises_runtime_error(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="No AI API key found"):
            detect_model()

    def test_priority_google_over_anthropic(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "g")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        model, provider = detect_model()
        assert provider == "google"

    def test_priority_anthropic_over_openai(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        model, provider = detect_model()
        assert provider == "anthropic"


class TestResolveModel:
    """Tests for _resolve_model()."""

    def test_empty_string_auto_detects(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test")
        model, provider = _resolve_model("")
        assert "gemini" in model.lower()
        assert provider == "google"

    def test_provider_model_format(self):
        model, provider = _resolve_model("anthropic:claude-3-opus")
        assert model == "claude-3-opus"
        assert provider == "anthropic"

    def test_provider_normalization_google_genai(self):
        model, provider = _resolve_model("google-genai:gemini-2.0-flash")
        assert model == "gemini-2.0-flash"
        assert provider == "google"

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


class TestGetApiKey:
    """Tests for _get_api_key() in plan_agent."""

    def test_returns_google_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-abc")
        assert _get_api_key("google") == "gk-abc"

    def test_returns_google_key_via_google_genai_alias(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-xyz")
        assert _get_api_key("google-genai") == "gk-xyz"

    def test_returns_anthropic_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        assert _get_api_key("anthropic") == "sk-ant-test"

    def test_returns_openai_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-test")
        assert _get_api_key("openai") == "sk-oai-test"

    def test_returns_none_for_unknown_provider(self, monkeypatch):
        monkeypatch.delenv("UNKNOWN_KEY", raising=False)
        assert _get_api_key("unknown_provider_xyz") is None

    def test_returns_none_when_env_var_unset(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        assert _get_api_key("google") is None

    def test_returns_deepseek_key(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
        assert _get_api_key("deepseek") == "ds-key"

    def test_returns_mistral_key(self, monkeypatch):
        monkeypatch.setenv("MISTRAL_API_KEY", "mi-key")
        assert _get_api_key("mistral") == "mi-key"


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


class TestDetectModelWithMasterAgent:
    """Tests for detect_model() when master_agent has an explicit model set."""

    def test_explicit_master_model_takes_priority(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "gk-test")
        from unittest.mock import patch

        with patch("dashboard.master_agent.is_master_model_explicit", return_value=True), \
             patch("dashboard.master_agent.get_master_config") as mock_cfg:
            mock_cfg.return_value = type("Cfg", (), {"model": "gpt-4o", "provider": "openai"})()
            model, provider = detect_model()
            assert model == "gpt-4o"
            assert provider == "openai"

    def test_explicit_master_model_with_slash_in_model(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        from unittest.mock import patch

        with patch("dashboard.master_agent.is_master_model_explicit", return_value=True), \
             patch("dashboard.master_agent.get_master_config") as mock_cfg:
            mock_cfg.return_value = type("Cfg", (), {"model": "anthropic/claude-opus-4", "provider": None})()
            model, provider = detect_model()
            assert model == "claude-opus-4"
            assert provider == "anthropic"

    def test_explicit_master_model_no_provider_bare_name(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        from unittest.mock import patch

        with patch("dashboard.master_agent.is_master_model_explicit", return_value=True), \
             patch("dashboard.master_agent.get_master_config") as mock_cfg:
            mock_cfg.return_value = type("Cfg", (), {"model": "my-custom-model", "provider": None})()
            model, provider = detect_model()
            assert model == "my-custom-model"
            assert provider is None

    def test_falls_through_to_env_when_not_explicit(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from unittest.mock import patch

        with patch("dashboard.master_agent.is_master_model_explicit", return_value=False):
            model, provider = detect_model()
            assert "claude" in model.lower()
            assert provider == "anthropic"
