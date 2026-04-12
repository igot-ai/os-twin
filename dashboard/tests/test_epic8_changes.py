import os
import sys
import httpx
import subprocess
from pathlib import Path


DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:9000")
API_KEY = os.environ.get("OSTWIN_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}

def setup_git_repo(path: Path):
    """Set up a temporary git repo with some commits."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    
    # Commit 1
    (path / "file1.txt").write_text("Hello World\n")
    subprocess.run(["git", "add", "file1.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=path, check=True)
    
    # Commit 2
    (path / "file1.txt").write_text("Hello World\nModified content\n")
    (path / "file2.txt").write_text("New file\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "Updated file1 and added file2"], cwd=path, check=True)
    
    # Uncommitted change
    (path / "file3.txt").write_text("Untracked file\n")
    (path / "file1.txt").write_text("Hello World\nModified content\nUncommitted change\n")

def test_unified_changes_timeline():
    print("Testing unified changes timeline (EPIC-008)...")
    
    test_repo = Path("/tmp/test-epic8-repo")
    if test_repo.exists():
        import shutil
        shutil.rmtree(test_repo)
    setup_git_repo(test_repo)
    
    with httpx.Client(base_url=DASHBOARD_URL, timeout=15, headers=HEADERS) as client:
        # 1. Create plan
        print("  - Creating plan...")
        resp = client.post("/api/plans/create", json={
            "path": str(test_repo),
            "title": "EPIC-008 Test Plan",
            "content": "# Plan: EPIC-008 Test Plan\n\n> Status: draft\n\n## Goal\nTest asset changes.",
            "working_dir": str(test_repo),
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        plan_id = resp.json()["plan_id"]
        print(f"    ✓ Plan created: {plan_id}")

        # 2. Get changes timeline
        print("  - Fetching changes timeline...")
        resp = client.get(f"/api/plans/{plan_id}/changes")
        assert resp.status_code == 200
        data = resp.json()
        changes = data["changes"]
        
        # Verify uncommitted changes exist
        uncommitted = next((c for c in changes if c.get("is_uncommitted")), None)
        assert uncommitted is not None, "Should find uncommitted changes"
        assert "file3.txt" in uncommitted["files"]
        assert "file1.txt" in uncommitted["files"]
        print("    ✓ Found uncommitted changes")
        
        # Verify git commits exist
        commits = [c for c in changes if c["source"] == "git" and not c.get("is_uncommitted")]
        assert len(commits) >= 2, f"Expected at least 2 commits, found {len(commits)}"
        assert commits[0]["message"] == "Updated file1 and added file2"
        assert commits[1]["message"] == "Initial commit"
        print("    ✓ Found git commits")

        # 3. Create a plan version by saving
        print("  - Creating plan version...")
        resp = client.post(f"/api/plans/{plan_id}/save", json={
            "content": "# Plan: EPIC-008 Test Plan v2\n\nUpdated content.",
            "change_source": "manual_save"
        })
        assert resp.status_code == 200
        
        # 4. Re-fetch changes and verify unified timeline
        print("  - Verifying unified timeline...")
        resp = client.get(f"/api/plans/{plan_id}/changes")
        assert resp.status_code == 200
        changes = resp.json()["changes"]
        
        # Should have plan version and git changes
        version_entry = next((c for c in changes if c["type"] == "plan_version"), None)
        assert version_entry is not None, "Should find plan version entry"
        assert version_entry["version"] == 1
        print("    ✓ Found plan version in timeline")
        
        # Verify sorting (latest first)
        timestamps = [c["timestamp"] for c in changes]
        assert timestamps == sorted(timestamps, reverse=True), "Timeline not sorted by timestamp desc"
        print("    ✓ Timeline correctly sorted")

        # 5. Test Diff for git commit
        print("  - Testing git commit diff...")
        commit_id = commits[0]["id"]
        resp = client.get(f"/api/plans/{plan_id}/changes/{commit_id}/diff")
        assert resp.status_code == 200
        diff_data = resp.json()
        assert "diff" in diff_data
        assert "Modified content" in diff_data["diff"]
        print("    ✓ Git commit diff successful")

        # 6. Test Diff for plan version
        print("  - Testing plan version diff...")
        version_id = version_entry["id"]
        resp = client.get(f"/api/plans/{plan_id}/changes/{version_id}/diff")
        assert resp.status_code == 200
        diff_data = resp.json()
        assert "diff" in diff_data
        # v1 should contain the ORIGINAL content (the one from /api/plans/create)
        assert "Test asset changes." in diff_data["diff"]
        print("    ✓ Plan version diff successful")

    print("\n✅ EPIC-008 Verification PASSED")

if __name__ == "__main__":
    try:
        test_unified_changes_timeline()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
