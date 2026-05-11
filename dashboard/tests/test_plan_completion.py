import json
from unittest.mock import AsyncMock

import pytest

from dashboard import plan_completion


@pytest.mark.asyncio
async def test_mark_plan_completed_broadcasts_once(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_completion, "PLANS_DIR", tmp_path)
    monkeypatch.setattr(plan_completion, "GLOBAL_PLANS_DIR", tmp_path)

    meta_path = tmp_path / "plan-1.meta.json"
    meta_path.write_text(json.dumps({"plan_id": "plan-1", "title": "Ship it", "status": "active"}))

    broadcast = AsyncMock()
    notify = AsyncMock()
    monkeypatch.setattr(plan_completion.global_state.broadcaster, "broadcast", broadcast)
    monkeypatch.setattr(plan_completion, "process_notification", notify)

    progress = {"total": 2, "passed": 2, "pct_complete": 100}
    first = await plan_completion.mark_plan_completed("plan-1", progress=progress, source="test")
    second = await plan_completion.mark_plan_completed("plan-1", progress=progress, source="test")

    assert first is True
    assert second is False
    broadcast.assert_awaited_once()
    notify.assert_awaited_once()

    event_name, payload = broadcast.await_args.args
    assert event_name == "plan_completed"
    assert payload["plan"]["plan_id"] == "plan-1"
    assert payload["plan"]["title"] == "Ship it"
    assert payload["progress"] == progress

    saved = json.loads(meta_path.read_text())
    assert saved["status"] == "completed"
    assert saved["completion_broadcast_at"]


def test_progress_is_completed_requires_passed_total():
    assert plan_completion.progress_is_completed({"total": 2, "passed": 2})
    assert not plan_completion.progress_is_completed({"total": 2, "passed": 1})
    assert not plan_completion.progress_is_completed({"total": 0, "passed": 0})
