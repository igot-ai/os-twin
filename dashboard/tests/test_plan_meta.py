"""
test_plan_meta.py — Verify that /api/plans/create produces meta.json
and that GET /api/plans/{plan_id} merges meta into the response.

Usage:
    python test_plan_meta.py              # runs against http://localhost:3366
    DASHBOARD_URL=http://localhost:9001 python test_plan_meta.py
"""

import os
import sys
import json
import httpx
from fastapi.testclient import TestClient
from dashboard.api import app
from dotenv import load_dotenv
from pathlib import Path as pathlib_Path

_env = pathlib_Path.home() / ".ostwin" / ".env"
if _env.is_file():
    load_dotenv(_env, override=True)
import time

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3366")

sys.path.insert(0, str(pathlib_Path(__file__).resolve().parent.parent.parent))
from dashboard.api_utils import PLANS_DIR


def test_create_plan_produces_meta_json():
    """POST /api/plans/create should create {plan_id}.meta.json."""
    title = f"Test Plan Meta {int(time.time())}"
    working_dir = "/tmp/test-plan-meta"

    API_KEY = os.environ.get("OSTWIN_API_KEY", "")
    HEADERS = {"X-API-Key": API_KEY}
    with TestClient(app, headers=HEADERS) as client:
        # --- 1. Create plan ---
        resp = client.post("/api/plans/create", json={
            "path": working_dir,
            "title": title,
            "working_dir": working_dir,
        })
        assert resp.status_code == 200, f"Create failed: {resp.status_code} {resp.text}"
        data = resp.json()
        plan_id = data.get("plan_id")
        assert plan_id, f"No plan_id in response: {data}"
        print(f"  ✓ Created plan: {plan_id}")

        # --- 2. Verify response shape ---
        assert "url" in data, f"Missing 'url' in response: {data}"
        assert "filename" in data, f"Missing 'filename' in response: {data}"
        assert data["filename"] == f"{plan_id}.md", f"Unexpected filename: {data['filename']}"
        print(f"  ✓ Response shape OK")

        # --- 3. Verify meta.json exists on disk ---
        meta_file = PLANS_DIR / f"{plan_id}.meta.json"
        assert meta_file.exists(), f"meta.json not found: {meta_file}"

        meta = json.loads(meta_file.read_text())
        required_fields = ["plan_id", "title", "working_dir", "warrooms_dir", "status", "created_at"]
        for field in required_fields:
            assert field in meta, f"Missing field '{field}' in meta.json: {meta}"
        assert meta["plan_id"] == plan_id
        assert meta["title"] == title
        assert meta["working_dir"] == working_dir
        assert meta["status"] == "draft"
        print(f"  ✓ meta.json has all required fields")

        # --- 4. Verify .md file exists ---
        plan_file = PLANS_DIR / f"{plan_id}.md"
        assert plan_file.exists(), f"Plan .md not found: {plan_file}"
        content = plan_file.read_text()
        assert title in content, f"Title not found in plan content"
        print(f"  ✓ Plan .md exists with correct content")

        # --- 5. GET /api/plans/{plan_id} merges meta ---
        resp = client.get(f"/api/plans/{plan_id}")
        assert resp.status_code == 200, f"GET failed: {resp.status_code} {resp.text}"
        get_data = resp.json()
        plan_obj = get_data.get("plan", {})
        assert plan_obj.get("plan_id") == plan_id
        assert plan_obj.get("working_dir") == working_dir, f"working_dir not merged: {plan_obj}"
        assert "meta" in plan_obj, f"No 'meta' key in GET response: {plan_obj}"
        assert plan_obj["meta"]["plan_id"] == plan_id
        assert plan_obj["meta"]["working_dir"] == working_dir
        print(f"  ✓ GET /api/plans/{plan_id} merges meta correctly")

        # --- Cleanup: remove test files ---
        try:
            meta_file.unlink(missing_ok=True)
            plan_file.unlink(missing_ok=True)
            roles_file = PLANS_DIR / f"{plan_id}.roles.json"
            roles_file.unlink(missing_ok=True)
            print(f"  ✓ Cleaned up test files")
        except Exception as e:
            print(f"  ⚠ Cleanup warning: {e}")

    print(f"\n✅ All assertions passed for plan {plan_id}")
    return True


def main():
    print(f"Testing against: {DASHBOARD_URL}")
    print(f"AGENTS_DIR: {AGENTS_DIR}")
    print(f"PLANS_DIR: {PLANS_DIR}")
    print()

    # Quick health check
    try:
        resp = httpx.get(f"{DASHBOARD_URL}/api/status", timeout=5)
        if resp.status_code != 200:
            print(f"⚠ Dashboard returned {resp.status_code} for /api/status")
    except httpx.ConnectError:
        print(f"✗ Cannot connect to {DASHBOARD_URL}. Is the dashboard running?")
        print(f"  Start with: ostwin dashboard")
        sys.exit(1)

    print("--- Test: create_plan_produces_meta_json ---")
    try:
        test_create_plan_produces_meta_json()
    except AssertionError as e:
        print(f"\n✗ FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        sys.exit(1)

    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    main()

