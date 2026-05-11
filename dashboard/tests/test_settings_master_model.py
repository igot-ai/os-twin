"""
Tests for the master-model settings endpoints added in this branch:
  GET  /api/settings/master-model
  PUT  /api/settings/master-model

These endpoints let the frontend read and update the global LLM model
used by the plan-refinement and brainstorm features.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from dashboard.api import app
from dashboard.auth import get_current_user


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_master_state():
    """Reset _master_config singleton before/after each test."""
    from dashboard import master_agent as ma

    saved = (
        ma._master_config.model,
        ma._master_config.provider,
        ma._master_config.temperature,
        ma._master_config.max_tokens,
        ma._master_config.is_explicit,
    )
    yield
    (
        ma._master_config.model,
        ma._master_config.provider,
        ma._master_config.temperature,
        ma._master_config.max_tokens,
        ma._master_config.is_explicit,
    ) = saved


@pytest.fixture
def client():
    """Authenticated test client (auth bypassed)."""
    app.dependency_overrides[get_current_user] = lambda: {"username": "test-user"}
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauth_client():
    """Unauthenticated test client."""
    app.dependency_overrides.clear()
    return TestClient(app)


# ── GET /api/settings/master-model ──────────────────────────────────────────


class TestGetMasterModel:
    def test_returns_default_model(self, client):
        from dashboard.master_agent import DEFAULT_MODEL

        resp = client.get("/api/settings/master-model")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == DEFAULT_MODEL

    def test_returns_updated_model_after_set(self, client):
        from dashboard.master_agent import set_master_model

        set_master_model("gpt-4o", provider="openai")
        resp = client.get("/api/settings/master-model")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "gpt-4o"
        assert data["provider"] == "openai"

    def test_response_schema_has_model_field(self, client):
        resp = client.get("/api/settings/master-model")
        assert "model" in resp.json()

    def test_requires_authentication(self, unauth_client):
        resp = unauth_client.get("/api/settings/master-model")
        # 401 or 403 depending on auth middleware
        assert resp.status_code in (401, 403)


# ── PUT /api/settings/master-model ──────────────────────────────────────────


class TestSetMasterModel:
    def test_set_model_plain(self, client):
        resp = client.put(
            "/api/settings/master-model",
            json={"model": "gpt-4o"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "gpt-4o"

    def test_set_model_with_provider(self, client):
        resp = client.put(
            "/api/settings/master-model",
            json={"model": "claude-3-opus", "provider": "anthropic"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "claude-3-opus"
        assert data["provider"] == "anthropic"

    def test_set_model_provider_is_optional(self, client):
        resp = client.put(
            "/api/settings/master-model",
            json={"model": "gemini-pro"},
        )
        assert resp.status_code == 200
        assert resp.json()["model"] == "gemini-pro"

    def test_set_model_persists_across_get(self, client):
        client.put(
            "/api/settings/master-model",
            json={"model": "my-custom-model", "provider": "custom"},
        )
        resp = client.get("/api/settings/master-model")
        assert resp.status_code == 200
        assert resp.json()["model"] == "my-custom-model"

    def test_set_model_missing_model_field_returns_422(self, client):
        resp = client.put(
            "/api/settings/master-model",
            json={"provider": "openai"},  # no "model" key
        )
        assert resp.status_code == 422

    def test_set_model_requires_authentication(self, unauth_client):
        resp = unauth_client.put(
            "/api/settings/master-model",
            json={"model": "gpt-4o"},
        )
        assert resp.status_code in (401, 403)

    def test_set_model_with_slash_prefix_parses_correctly(self, client):
        """Provider prefix embedded in model string should be parsed by set_master_model."""
        resp = client.put(
            "/api/settings/master-model",
            json={"model": "openai/gpt-4-turbo"},
        )
        assert resp.status_code == 200
        # The endpoint passes the raw model to set_master_model which parses the prefix
        from dashboard.master_agent import get_master_config
        cfg = get_master_config()
        assert cfg.model == "gpt-4-turbo"
        assert cfg.provider == "openai"

    def test_set_model_persists_to_config_json(self, client):
        """PUT /master-model should write to config.json via resolver so settings survive restarts."""
        mock_resolver = MagicMock()
        with patch("dashboard.lib.settings.get_settings_resolver", return_value=mock_resolver):
            resp = client.put(
                "/api/settings/master-model",
                json={"model": "gpt-4-turbo", "provider": "openai"},
            )
        assert resp.status_code == 200
        mock_resolver.patch_namespace.assert_called_once_with(
            "runtime", {"master_agent_model": "openai/gpt-4-turbo"}
        )

    def test_set_model_plain_persists_to_config_json(self, client):
        """PUT /master-model with no provider should still persist to config.json."""
        mock_resolver = MagicMock()
        with patch("dashboard.lib.settings.get_settings_resolver", return_value=mock_resolver):
            resp = client.put(
                "/api/settings/master-model",
                json={"model": "llama3.2"},
            )
        assert resp.status_code == 200
        mock_resolver.patch_namespace.assert_called_once_with(
            "runtime", {"master_agent_model": "llama3.2"}
        )
