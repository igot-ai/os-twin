"""Unit tests for dashboard/ai/errors.py.

Covers:
  - Error class hierarchy (AIError base, subclass relationships)
  - isinstance checks across hierarchy
  - Message string propagation
  - Raise-and-catch semantics for each type
"""

from __future__ import annotations

import pytest

from dashboard.ai.errors import AIAuthError, AIError, AIQuotaError, AITimeoutError


class TestErrorHierarchy:
    def test_ai_error_is_base_exception(self):
        assert issubclass(AIError, Exception)

    def test_auth_error_is_ai_error(self):
        assert issubclass(AIAuthError, AIError)

    def test_timeout_error_is_ai_error(self):
        assert issubclass(AITimeoutError, AIError)

    def test_quota_error_is_ai_error(self):
        assert issubclass(AIQuotaError, AIError)

    def test_auth_error_is_not_timeout_error(self):
        """Subclasses must not be confused with each other."""
        assert not issubclass(AIAuthError, AITimeoutError)

    def test_message_propagates(self):
        msg = "API key expired"
        exc = AIAuthError(msg)
        assert str(exc) == msg

    def test_raise_and_catch_base_class(self):
        """Catching AIError must catch all subclasses."""
        with pytest.raises(AIError):
            raise AITimeoutError("timed out")

    def test_raise_and_catch_specific_type(self):
        with pytest.raises(AITimeoutError):
            raise AITimeoutError("request timed out after 60s")

    def test_quota_error_raised_and_caught(self):
        with pytest.raises(AIQuotaError, match="rate limit"):
            raise AIQuotaError("rate limit exceeded")

    def test_isinstance_checks(self):
        err = AIAuthError("bad creds")
        assert isinstance(err, AIError)
        assert isinstance(err, AIAuthError)
        assert not isinstance(err, AITimeoutError)
        assert not isinstance(err, AIQuotaError)
