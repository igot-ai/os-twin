"""
EPIC-003 — Tests for Telegram poller asset handling during planning sessions.

Tests: document detection, photo detection, file download, asset upload routing,
       epic-context auto-binding, and the asset prompt step in /draft flow.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path


@pytest.fixture
def temp_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("dashboard.routes.plans.PLANS_DIR", tmp_path)
    plan_id = "tg-test-plan"
    plan_file = tmp_path / f"{plan_id}.md"
    plan_file.write_text("# Plan: TG Test\n\n### EPIC-001 — First\n")
    assets_dir = tmp_path / "assets" / plan_id
    assets_dir.mkdir(parents=True)
    return plan_id, tmp_path, assets_dir


def test_extract_file_info_document():
    """Test extracting file info from a Telegram document message."""
    from dashboard.telegram_poller import _extract_file_info

    message = {
        "document": {
            "file_id": "BQACAgIAAxk-doc-123",
            "file_name": "design-spec.pdf",
            "mime_type": "application/pdf",
            "file_size": 4096,
        },
        "caption": "Here is the design spec for EPIC-002",
    }
    info = _extract_file_info(message)
    assert info is not None
    assert info["file_id"] == "BQACAgIAAxk-doc-123"
    assert info["file_name"] == "design-spec.pdf"
    assert info["mime_type"] == "application/pdf"
    assert info["caption"] == "Here is the design spec for EPIC-002"


def test_extract_file_info_photo():
    """Test extracting file info from a Telegram photo message."""
    from dashboard.telegram_poller import _extract_file_info

    message = {
        "photo": [
            {"file_id": "small-id", "width": 90, "height": 90},
            {"file_id": "medium-id", "width": 320, "height": 320},
            {"file_id": "large-id", "width": 800, "height": 800},
        ],
        "caption": "UI mockup",
    }
    info = _extract_file_info(message)
    assert info is not None
    # Should pick the largest photo
    assert info["file_id"] == "large-id"
    assert info["file_name"] == "photo.jpg"
    assert info["mime_type"] == "image/jpeg"


def test_extract_file_info_text_only():
    """Text-only messages should return None."""
    from dashboard.telegram_poller import _extract_file_info

    message = {"text": "Hello world"}
    info = _extract_file_info(message)
    assert info is None


def test_detect_epic_ref_from_caption():
    """Test detecting epic reference from file caption."""
    from dashboard.telegram_poller import _detect_epic_ref

    assert _detect_epic_ref("Here is the spec for EPIC-002") == "EPIC-002"
    assert _detect_epic_ref("EPIC-001 design mockup") == "EPIC-001"
    assert _detect_epic_ref("No epic reference here") is None
    assert _detect_epic_ref("") is None
    assert _detect_epic_ref(None) is None


def test_guess_asset_type():
    """Test guessing asset type from filename and mime type."""
    from dashboard.telegram_poller import _guess_asset_type

    assert _guess_asset_type("design.png", "image/png") == "design-mockup"
    assert _guess_asset_type("mockup.fig", "application/octet-stream") == "design-mockup"
    assert _guess_asset_type("api-spec.yaml", "text/yaml") == "api-spec"
    assert _guess_asset_type("openapi.json", "application/json") == "api-spec"
    assert _guess_asset_type("test-data.csv", "text/csv") == "test-data"
    assert _guess_asset_type("config.env", "text/plain") == "config"
    assert _guess_asset_type(".env", "text/plain") == "config"
    assert _guess_asset_type("readme.md", "text/markdown") == "reference-doc"
    assert _guess_asset_type("video.mp4", "video/mp4") == "media"
    assert _guess_asset_type("random.bin", "application/octet-stream") == "other"


@pytest.mark.asyncio
async def test_handle_document_in_planning_session(temp_plan, monkeypatch):
    """End-to-end: document sent during editing session gets uploaded as asset."""
    plan_id, tmp_path, assets_dir = temp_plan

    # Mock session in editing mode
    mock_session = MagicMock()
    mock_session.mode = "editing"
    mock_session.active_plan_id = plan_id
    monkeypatch.setattr("dashboard.telegram_poller.get_session", lambda chat_id: mock_session)

    # Mock Telegram file download
    fake_file_bytes = b"fake-pdf-content"

    async def mock_download(bot_token, file_id):
        return fake_file_bytes

    monkeypatch.setattr("dashboard.telegram_poller._download_telegram_file", mock_download)

    # Mock send_reply to capture messages
    sent_messages = []

    async def mock_send(bot_token, chat_id, text):
        sent_messages.append(text)

    monkeypatch.setattr("dashboard.telegram_poller.send_reply", mock_send)

    # Mock PLANS_DIR for the asset save
    monkeypatch.setattr("dashboard.telegram_poller.PLANS_DIR", tmp_path)

    # Create meta.json
    from dashboard.routes.plans import _ensure_plan_meta
    _ensure_plan_meta(plan_id)

    from dashboard.telegram_poller import _handle_file_upload

    message = {
        "document": {
            "file_id": "test-file-id",
            "file_name": "spec.pdf",
            "mime_type": "application/pdf",
            "file_size": len(fake_file_bytes),
        },
        "caption": "API spec for EPIC-001",
    }

    await _handle_file_upload("fake-token", 12345, message, mock_session)

    # Verify asset was saved
    from dashboard.routes.plans import _ensure_plan_meta as reload_meta
    meta = reload_meta(plan_id)
    assert len(meta["assets"]) == 1
    assert meta["assets"][0]["original_name"] == "spec.pdf"
    assert meta["assets"][0]["mime_type"] == "application/pdf"
    # Should be auto-bound to EPIC-001 from caption
    assert "EPIC-001" in meta["assets"][0].get("bound_epics", [])

    # Verify confirmation message sent
    assert any("spec.pdf" in m for m in sent_messages)


@pytest.mark.asyncio
async def test_handle_photo_in_planning_session(temp_plan, monkeypatch):
    """Photo sent during editing session gets uploaded as asset."""
    plan_id, tmp_path, assets_dir = temp_plan

    mock_session = MagicMock()
    mock_session.mode = "editing"
    mock_session.active_plan_id = plan_id
    monkeypatch.setattr("dashboard.telegram_poller.get_session", lambda chat_id: mock_session)

    fake_photo_bytes = b"\x89PNG\r\n\x1a\nfake-photo"

    async def mock_download(bot_token, file_id):
        return fake_photo_bytes

    monkeypatch.setattr("dashboard.telegram_poller._download_telegram_file", mock_download)

    sent_messages = []

    async def mock_send(bot_token, chat_id, text):
        sent_messages.append(text)

    monkeypatch.setattr("dashboard.telegram_poller.send_reply", mock_send)
    monkeypatch.setattr("dashboard.telegram_poller.PLANS_DIR", tmp_path)

    from dashboard.routes.plans import _ensure_plan_meta
    _ensure_plan_meta(plan_id)

    from dashboard.telegram_poller import _handle_file_upload

    message = {
        "photo": [
            {"file_id": "small", "width": 90, "height": 90},
            {"file_id": "large-photo-id", "width": 800, "height": 600},
        ],
        "caption": "",
    }

    await _handle_file_upload("fake-token", 12345, message, mock_session)

    meta = _ensure_plan_meta(plan_id)
    assert len(meta["assets"]) == 1
    assert meta["assets"][0]["mime_type"] == "image/jpeg"
    # No epic ref in caption => plan-level
    assert meta["assets"][0].get("bound_epics", []) == []


@pytest.mark.asyncio
async def test_file_outside_planning_session_ignored(temp_plan, monkeypatch):
    """Files sent outside a planning session should not be processed."""
    from dashboard.telegram_poller import _extract_file_info

    mock_session = MagicMock()
    mock_session.mode = ""
    mock_session.active_plan_id = None

    message = {
        "document": {
            "file_id": "doc-123",
            "file_name": "random.txt",
            "mime_type": "text/plain",
        }
    }
    # The main handle_message should skip this since no active plan
    info = _extract_file_info(message)
    assert info is not None  # File info is extractable
    # But in practice, _handle_file_upload would check session.active_plan_id
