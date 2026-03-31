# Path Traversal Variant Analysis — Phase 10

**Date:** 2026-03-30
**Analyst:** Variant Hunter (Phase 10)
**Origin Findings:**
- `security/findings-draft/p8-025-fe-catch-all-path-traversal.md` (Pattern AP-025, Severity: HIGH)
- `security/findings-draft/p8-043-mcp-room-dir-path-traversal.md` (Pattern AP-043, Severity: HIGH)

---

## Search Strategy Applied

### Detection Signatures Used
- `os\.path\.join|Path\(|os\.makedirs|open\(|FileResponse|listdir|os\.walk|glob\.glob` — grep across all Python files
- Manual trace of user-controlled path parameters in all FastAPI route handlers
- Manual trace of `room_dir` parameter usage in all MCP server tools
- Review of `is_relative_to` / `realpath` / containment check usage across the codebase

### Files Audited
All 85 Python files in the repository. High-signal targets:
- `dashboard/routes/plans.py` — plan create/launch/read operations
- `dashboard/routes/rooms.py` — war-room channel reads
- `dashboard/routes/skills.py` — skill install/read
- `dashboard/routes/system.py` — filesystem browser endpoint
- `.agents/mcp/warroom-server.py` — MCP war-room tools (update_status, list_artifacts, report_progress)
- `.agents/mcp/channel-server.py` — MCP channel tools (post_message, read_messages, get_latest)

---

## Confirmed Variants

### Variant 1: Filesystem Browser — Arbitrary Directory Enumeration
**Finding:** `security/findings-draft/p10-050-fs-browse-path-traversal.md`
**Location:** `dashboard/routes/system.py:273-295`
**Endpoint:** `GET /api/fs/browse?path=<user-supplied>`
**Root Cause:** `Path(path).expanduser().resolve()` + `target.iterdir()` with no containment check
**Attacker Control:** Full — any absolute or relative path accepted in `path` query parameter
**Auth Required:** Yes (valid session token) — severity stays MEDIUM due to auth gate
**Severity:** MEDIUM
**Pattern:** AP-025

**Code Path:**
```
GET /api/fs/browse?path=/etc
  -> browse_filesystem(path="/etc", user=...)
  -> target = Path("/etc").expanduser().resolve()   # no containment check
  -> for entry in sorted(target.iterdir()):         # lists /etc/*
  -> dirs.append({"name": entry.name, "path": str(entry), ...})
  -> return {"current": "/etc", "dirs": [...]}
```

**No blocking protection.** The only check is `target.exists() and target.is_dir()` — this confirms traversal works rather than blocking it.

---

### Variant 2: Skill Install — Arbitrary Path File Read
**Finding:** `security/findings-draft/p10-051-skills-install-path-traversal.md`
**Location:** `dashboard/routes/skills.py:132-160`
**Endpoint:** `POST /api/skills/install` with body `{"path": "<user-supplied>"}`
**Root Cause:** `Path(req.path)` used to read SKILL.md from any filesystem location
**Attacker Control:** Full — `req.path` is a free-form string from the request body
**Auth Required:** Yes — severity stays MEDIUM
**Severity:** MEDIUM
**Pattern:** AP-025

**Code Path:**
```
POST /api/skills/install {"path": "/tmp/attacker-dir"}
  -> install_skill(req.path="/tmp/attacker-dir", user=...)
  -> path = Path("/tmp/attacker-dir")
  -> skill_md = path / "SKILL.md"                   # reads /tmp/attacker-dir/SKILL.md
  -> data = parse_skill_md(path)                    # full content parsed and indexed
  -> store.index_skill(content=data["content"])     # content stored in vector DB
  -> return {"status": "installed", "skill": name}  # content retrievable via search
```

**Note:** `api_utils.py:330-342` contains an `is_relative_to` check but it is used only for **metadata classification** (determining `source` field value), not for access control.

---

### Variant 3: MCP list_artifacts — Arbitrary Directory Walk
**Finding:** `security/findings-draft/p10-052-warroom-list-artifacts-path-traversal.md`
**Location:** `.agents/mcp/warroom-server.py:87-116`
**Tool:** `list_artifacts(room_dir=<user-supplied>)`
**Root Cause:** `os.path.join(room_dir, "artifacts")` + `os.walk()` with no containment check
**Attacker Control:** Full — `room_dir` is a free-form MCP parameter
**Auth Required:** MCP client access (direct or via prompt injection)
**Severity:** MEDIUM
**Pattern:** AP-043

**Code Path:**
```
list_artifacts(room_dir="../../../../tmp/probe")
  -> artifacts_dir = os.path.join("../../../../tmp/probe", "artifacts")
  -> if not os.path.exists(artifacts_dir): return "[]"   # oracle: confirms path existence
  -> for root, _dirs, fnames in os.walk(artifacts_dir):  # full recursive walk
  ->   stat = os.stat(full_path)
  ->   files.append({"path": rel_path, "size_bytes": ..., "modified": ...})
  -> return json.dumps(files)
```

**Chaining potential:** Use `update_status` (p8-043) to create target directory structure, then populate `artifacts/` subdirectory, then enumerate with `list_artifacts`.

---

### Variant 4: MCP read_messages / get_latest — Arbitrary File Read
**Finding:** `security/findings-draft/p10-053-channel-server-read-path-traversal.md`
**Location:** `.agents/mcp/channel-server.py:136,179`
**Tools:** `read_messages(room_dir=<user-supplied>)`, `get_latest(room_dir=<user-supplied>)`
**Root Cause:** `os.path.join(room_dir, "channel.jsonl")` + `open(..., "r")` with no containment check
**Attacker Control:** Full — `room_dir` is a free-form MCP parameter
**Auth Required:** MCP client access (direct or via prompt injection)
**Severity:** HIGH — closes a full read/write cycle with p8-043's write primitive, enabling covert data exfiltration
**Pattern:** AP-043

**Code Path:**
```
read_messages(room_dir="../../../../tmp/exfil")
  -> channel_file = os.path.join("../../../../tmp/exfil", "channel.jsonl")
  -> if not os.path.exists(channel_file): return "[]"
  -> with open(channel_file, "r") as f:              # reads arbitrary file
  ->   for line in f:
  ->     msg = json.loads(line)                      # returns valid JSON lines
  ->     messages.append(msg)
  -> return json.dumps(messages)
```

**Critical chaining:** `post_message` (p8-043 confirmed write) writes attacker-controlled `body` to `channel.jsonl` at any path. `read_messages` reads it back. This gives full covert read/write file primitive pairs.

---

## Ruled-Out Candidates

### `dashboard/routes/plans.py` — `create_plan`
- `working_dir` and `warrooms_dir` are written to meta.json and used for progress.json reads
- These are user-controlled but only stored and read by the server; the paths are not directly resolved or returned as file contents in a read-through manner
- The `warrooms_dir` value written in meta could be a traversal path, but accessing it requires a subsequent plan launch — indirect and low severity vs. existing findings
- Not a blocking protection, but the indirection and multi-step requirement reduce it below variant threshold compared to confirmed findings

### `dashboard/routes/rooms.py` — `get_messages`
- `room_id` (URL path segment) is joined with `WARROOMS_DIR / room_id` — but `WARROOMS_DIR` is a hardcoded base
- The `{room_id}` value is a URL path segment, NOT a `{path:path}` converter — FastAPI will reject `/` in room_id via the URL router
- Fallback logic iterates plan meta files and reads `working_dir` from stored meta, then constructs the candidate path — this is server-controlled data, not directly attacker-controlled in this request

### `.agents/mcp/warroom-server.py` — `update_status` and `report_progress`
- Already confirmed in p8-043 (the origin finding)

### `.agents/mcp/channel-server.py` — `post_message`
- Already confirmed in p8-043 (the origin finding)

---

## Summary Table

| # | Slug | Location | Endpoint/Tool | Auth? | Severity | Pattern |
|---|------|----------|---------------|-------|----------|---------|
| p10-050 | fs-browse-path-traversal | system.py:273 | GET /api/fs/browse | Yes | MEDIUM | AP-025 |
| p10-051 | skills-install-path-traversal | skills.py:132 | POST /api/skills/install | Yes | MEDIUM | AP-025 |
| p10-052 | warroom-list-artifacts-path-traversal | warroom-server.py:87 | MCP list_artifacts | MCP | MEDIUM | AP-043 |
| p10-053 | channel-server-read-path-traversal | channel-server.py:136,179 | MCP read_messages/get_latest | MCP | HIGH | AP-043 |

**Total confirmed variants: 4**

---

## Remediation Pattern

All four variants share the same fix pattern: resolve the user-supplied path and verify containment before use.

```python
# Correct fix for all variants:
import os
from pathlib import Path

def safe_resolve(user_path: str, base_dir: Path) -> Path:
    resolved = (base_dir / user_path).resolve()
    if not resolved.is_relative_to(base_dir.resolve()):
        raise ValueError(f"Path traversal detected: {user_path!r}")
    return resolved
```

For `/api/fs/browse`, the appropriate base is a configurable root (e.g., `PROJECT_ROOT`) rather than allowing filesystem-wide access.

For MCP tools, `room_dir` should be resolved relative to a configured war-rooms base directory with a containment check before any `makedirs`, `open`, or `os.walk` call.
