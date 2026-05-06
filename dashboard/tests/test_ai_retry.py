"""Unit tests for dashboard/ai/retry.py.

Covers:
  - Success on first attempt (no retry)
  - Retry on generic Exception, then succeed
  - Exhaust all retries → re-raises last exception
  - AIAuthError is NOT retried (fail fast)
  - AITimeoutError is NOT retried (fail fast)
  - Backoff delay is applied between retries
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, call, patch

import pytest

from dashboard.ai.errors import AIAuthError, AITimeoutError, AIError
from dashboard.ai.retry import with_retry


# ---------------------------------------------------------------------------
# TestWithRetry
# ---------------------------------------------------------------------------


class TestWithRetry:
    def test_success_on_first_attempt_no_sleep(self):
        """Happy path: callable succeeds immediately, no sleep."""
        fn = MagicMock(return_value="ok")

        with patch("dashboard.ai.retry.time.sleep") as mock_sleep:
            result = with_retry(fn, max_retries=2)

        assert result == "ok"
        fn.assert_called_once()
        mock_sleep.assert_not_called()

    def test_retries_then_succeeds(self):
        """Fails twice, succeeds on third attempt."""
        attempts = {"count": 0}

        def flaky():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise AIError("transient failure")
            return "success"

        with patch("dashboard.ai.retry.time.sleep"):
            result = with_retry(flaky, max_retries=2)

        assert result == "success"
        assert attempts["count"] == 3

    def test_raises_last_exception_after_exhausting_retries(self):
        """After max_retries is exhausted, re-raises the final exception."""
        sentinel = AIError("always fails")
        fn = MagicMock(side_effect=sentinel)

        with patch("dashboard.ai.retry.time.sleep"):
            with pytest.raises(AIError, match="always fails"):
                with_retry(fn, max_retries=2)

        assert fn.call_count == 3  # initial + 2 retries

    def test_auth_error_not_retried(self):
        """AIAuthError must propagate immediately — bad creds won't fix themselves."""
        fn = MagicMock(side_effect=AIAuthError("bad key"))

        with patch("dashboard.ai.retry.time.sleep") as mock_sleep:
            with pytest.raises(AIAuthError):
                with_retry(fn, max_retries=3)

        fn.assert_called_once()
        mock_sleep.assert_not_called()

    def test_timeout_error_not_retried(self):
        """AITimeoutError must propagate immediately — retrying makes it worse."""
        fn = MagicMock(side_effect=AITimeoutError("timed out"))

        with patch("dashboard.ai.retry.time.sleep") as mock_sleep:
            with pytest.raises(AITimeoutError):
                with_retry(fn, max_retries=3)

        fn.assert_called_once()
        mock_sleep.assert_not_called()

    def test_backoff_delay_applied_between_retries(self):
        """time.sleep must be called with a positive value between retries."""
        fn = MagicMock(side_effect=[AIError("fail"), AIError("fail"), "ok"])

        sleep_calls = []

        def capture_sleep(delay):
            sleep_calls.append(delay)

        with patch("dashboard.ai.retry.time.sleep", side_effect=capture_sleep):
            # fn always raises so we exhaust retries
            fn2 = MagicMock(side_effect=AIError("always"))
            with pytest.raises(AIError):
                with_retry(fn2, max_retries=2, base_delay=0.1, max_delay=5.0)

        assert len(sleep_calls) == 2  # once per retry
        for delay in sleep_calls:
            assert delay > 0

    def test_zero_retries_calls_fn_exactly_once(self):
        """max_retries=0 means try once, then give up on any failure."""
        fn = MagicMock(side_effect=AIError("boom"))

        with patch("dashboard.ai.retry.time.sleep") as mock_sleep:
            with pytest.raises(AIError):
                with_retry(fn, max_retries=0)

        fn.assert_called_once()
        mock_sleep.assert_not_called()

    def test_returns_value_from_callable(self):
        """Result is passed through transparently."""
        expected = {"key": "value", "list": [1, 2, 3]}
        fn = MagicMock(return_value=expected)

        result = with_retry(fn, max_retries=1)
        assert result is expected
