"""Tests for dashboard/plan_agent.py — pure functions only (no LLM calls)."""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Stub out the `deepagents` module before importing plan_agent,
# since it is not installed in the test environment.
if "deepagents" not in sys.modules:
    sys.modules["deepagents"] = MagicMock()

from dashboard.plan_agent import (
    parse_structured_response,
    _load_available_roles,
    detect_model,
    _make_human_content,
    build_messages,
    get_system_prompt,
)
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage


# ── parse_structured_response ──────────────────────────────────────


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
        # The re.split strips the "# PLAN" header itself; content starts after it
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
        # re.split captures the PLAN header, so the plan content follows it
        assert "Revised" in result["plan"]
        assert "Content here." in result["plan"]

    def test_fallback_when_no_sections_but_looks_like_plan(self):
        text = "# Plan\n\n## Epics\n\n### EPIC-001\nDo something."
        result = parse_structured_response(text)
        # The regex splits on "# PLAN" (case-insensitive), which matches "# Plan"
        # So "Plan" is captured as a header and the rest is content.
        # The plan field gets the content after the PLAN header.
        assert result["actions"] == []
        # Either it matched the PLAN header or fell through to fallback
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


# ── _load_available_roles ──────────────────────────────────────────


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


# ── detect_model ───────────────────────────────────────────────────


class TestDetectModel:
    """Tests for detect_model()."""

    def test_google_api_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-google-key")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        model, provider = detect_model()
        assert model == "gemini-3-flash-preview"
        assert provider == "google_genai"

    def test_anthropic_api_key(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        model, provider = detect_model()
        assert model == "claude-sonnet-4-6"
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
        assert provider == "google_genai"

    def test_priority_anthropic_over_openai(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
        monkeypatch.setenv("OPENAI_API_KEY", "o")
        model, provider = detect_model()
        assert provider == "anthropic"


# ── _make_human_content ────────────────────────────────────────────


class TestMakeHumanContent:
    """Tests for _make_human_content()."""

    def test_no_images_returns_plain_text(self):
        result = _make_human_content("Hello world")
        assert result == "Hello world"

    def test_none_images_returns_plain_text(self):
        result = _make_human_content("Hello world", images=None)
        assert result == "Hello world"

    def test_empty_images_returns_plain_text(self):
        result = _make_human_content("Hello world", images=[])
        assert result == "Hello world"

    def test_with_images_returns_list_of_blocks(self):
        images = [{"url": "https://example.com/img.png"}]
        result = _make_human_content("Describe this", images)
        assert isinstance(result, list)
        assert result[0] == {"type": "text", "text": "Describe this"}
        assert result[1]["type"] == "image_url"
        assert result[1]["image_url"]["url"] == "https://example.com/img.png"

    def test_text_empty_but_images_present(self):
        images = [{"url": "https://example.com/a.png"}]
        result = _make_human_content("", images)
        assert isinstance(result, list)
        # No text block when text is empty
        assert len(result) == 1
        assert result[0]["type"] == "image_url"

    def test_multiple_images(self):
        images = [
            {"url": "https://example.com/a.png"},
            {"url": "https://example.com/b.png"},
        ]
        result = _make_human_content("Two images", images)
        assert isinstance(result, list)
        assert len(result) == 3  # 1 text + 2 images

    def test_image_without_url_key_skipped(self):
        images = [{"data": "base64..."}]  # no "url" key
        result = _make_human_content("Test", images)
        # Only the text block — image has no url so it's skipped
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "text"


# ── build_messages ─────────────────────────────────────────────────


class TestBuildMessages:
    """Tests for build_messages()."""

    def test_simple_message_only(self):
        msgs = build_messages("Hello")
        assert len(msgs) == 1
        assert isinstance(msgs[0], HumanMessage)
        assert msgs[0].content == "Hello"

    def test_with_plan_content(self):
        msgs = build_messages("Improve this", plan_content="# Plan: Foo")
        assert len(msgs) == 2
        assert isinstance(msgs[0], SystemMessage)
        assert "# Plan: Foo" in msgs[0].content
        assert isinstance(msgs[1], HumanMessage)
        assert msgs[1].content == "Improve this"

    def test_empty_plan_content_no_system_message(self):
        msgs = build_messages("Hello", plan_content="   ")
        assert len(msgs) == 1
        assert isinstance(msgs[0], HumanMessage)

    def test_with_chat_history(self):
        history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
        ]
        msgs = build_messages("Follow-up", chat_history=history)
        assert len(msgs) == 3
        assert isinstance(msgs[0], HumanMessage)
        assert msgs[0].content == "First question"
        assert isinstance(msgs[1], AIMessage)
        assert msgs[1].content == "First answer"
        assert isinstance(msgs[2], HumanMessage)
        assert msgs[2].content == "Follow-up"

    def test_with_images(self):
        images = [{"url": "https://example.com/img.png"}]
        msgs = build_messages("What's this?", images=images)
        assert len(msgs) == 1
        assert isinstance(msgs[0], HumanMessage)
        # Content should be multimodal list
        assert isinstance(msgs[0].content, list)

    def test_with_plan_and_history_and_images(self):
        history = [{"role": "user", "content": "Hi"}]
        images = [{"url": "https://example.com/x.png"}]
        msgs = build_messages(
            "Describe",
            plan_content="# Plan",
            chat_history=history,
            images=images,
        )
        # SystemMessage (plan) + HumanMessage (history) + HumanMessage (latest with images)
        assert len(msgs) == 3
        assert isinstance(msgs[0], SystemMessage)
        assert isinstance(msgs[1], HumanMessage)
        assert isinstance(msgs[2], HumanMessage)
        assert isinstance(msgs[2].content, list)


# ── get_system_prompt ──────────────────────────────────────────────


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
        # {{AVAILABLE_ROLES}} should be replaced
        assert "{{AVAILABLE_ROLES}}" not in prompt
        assert "Available roles" in prompt

    def test_plans_dir_without_template(self, tmp_path):
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        agents_dir = tmp_path
        # Create the fallback path too (should not exist)
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
