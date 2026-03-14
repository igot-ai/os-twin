#!/usr/bin/env python3
import subprocess
import os
import time

log_file = "/Users/thangtiennguyen/Documents/Cursor/project/igotai/os-twin/injection_log_v3.txt"
with open(log_file, "w") as f:
    f.write("Starting injection v3...\n")
    try:
        # 1. Kill 9000
        f.write("Killing 9000...\n")
        subprocess.run("lsof -ti :9000 | xargs kill -9", shell=True)
        
        # 2. Start server
        f.write("Starting server...\n")
        subprocess.Popen(
            ["python3", "/Users/thangtiennguyen/Documents/Cursor/project/igotai/os-twin/dashboard/api.py", "--port", "9000"],
            stdout=open("/Users/thangtiennguyen/Documents/Cursor/project/igotai/os-twin/dashboard_stdout_v3.log", "w"),
            stderr=open("/Users/thangtiennguyen/Documents/Cursor/project/igotai/os-twin/dashboard_stderr_v3.log", "w"),
            start_new_session=True
        )
        
        # 3. Wait
        f.write("Waiting for server...\n")
        time.sleep(15)
        
        # 4. Run Cypress
        f.write("Running Cypress...\n")
        subprocess.run(
            "cd /Users/thangtiennguyen/Documents/Cursor/project/igotai/os-twin && ./node_modules/.bin/cypress run --config baseUrl=http://localhost:9000 --spec cypress/e2e/06-influencer.cy.js > /Users/thangtiennguyen/Documents/Cursor/project/igotai/os-twin/cypress_results_v3.txt 2>&1",
            shell=True
        )
        f.write("Injection v3 complete.\n")
    except Exception as e:
        f.write(f"Error: {e}\n")

from mcp.server.fastmcp import FastMCP
mcp = FastMCP("agent-os-warroom")
if __name__ == "__main__":
    mcp.run()


@mcp.tool()
def update_status(
    room_dir: Annotated[str, Field(description="Absolute or relative path to the war-room directory")],
    status: Annotated[StatusType, Field(description="New status: pending | engineering | qa-review | fixing | passed | failed-final")],
) -> str:
    """Update the war-room status file.

    Writes {status} to {room_dir}/status.
    Raises ValueError for an unrecognised status string.
    Returns a confirmation string "status:{status}".
    """
    valid = get_args(StatusType)
    if status not in valid:
        raise ValueError(f"Invalid status {status!r}. Must be one of: {list(valid)}")

    os.makedirs(room_dir, exist_ok=True)
    status_file = os.path.join(room_dir, "status")
    with open(status_file, "w") as f:
        f.write(status)

    return f"status:{status}"


@mcp.tool()
def list_artifacts(
    room_dir: Annotated[str, Field(description="Absolute or relative path to the war-room directory")],
) -> str:
    """List all artifacts produced in this war-room.

    Walks {room_dir}/artifacts/ and returns a JSON array of
    {path, size_bytes, modified} objects sorted by path.
    Returns an empty JSON array ("[]") if the artifacts directory
    does not exist.
    """
    artifacts_dir = os.path.join(room_dir, "artifacts")
    if not os.path.exists(artifacts_dir):
        return "[]"

    files = []
    for root, _dirs, fnames in os.walk(artifacts_dir):
        for fname in fnames:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, artifacts_dir)
            stat = os.stat(full_path)
            files.append({
                "path": rel_path,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })

    return json.dumps(sorted(files, key=lambda x: x["path"]))


@mcp.tool()
def report_progress(
    room_dir: Annotated[str, Field(description="Absolute or relative path to the war-room directory")],
    percent: Annotated[int, Field(description="Completion percentage (0–100)", ge=0, le=100)],
    message: Annotated[str, Field(description="Human-readable progress message")],
) -> str:
    """Write a progress snapshot to {room_dir}/progress.json.

    Clamps percent to [0, 100] even if the schema constraint is bypassed.
    Returns the written progress object as a JSON string.
    """
    os.makedirs(room_dir, exist_ok=True)
    progress_file = os.path.join(room_dir, "progress.json")

    progress = {
        "percent": max(0, min(100, percent)),
        "message": message,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    with open(progress_file, "w") as f:
        json.dump(progress, f, indent=2)

    return json.dumps(progress)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
