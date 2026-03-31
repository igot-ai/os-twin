Phase: 10
Sequence: 051
Slug: skills-install-path-traversal
Verdict: VALID
Rationale: The /api/skills/install endpoint accepts an arbitrary filesystem path from the request body and reads SKILL.md from that path without containment checks, allowing any authenticated user to read files from arbitrary locations by constructing a SKILL.md at a target directory or probing the existence/content of files across the filesystem.
Severity-Original: MEDIUM
PoC-Status: pending
Origin-Finding: security/findings-draft/p8-025-fe-catch-all-path-traversal.md
Origin-Pattern: AP-025

## Summary

The `install_skill` handler (`dashboard/routes/skills.py:132-160`) accepts a `path` field in the request body and passes it directly to `Path(req.path)`. It then reads `SKILL.md` from that path via `parse_skill_md(path)` with no containment check. An attacker who can place a valid `SKILL.md` file in a directory of interest (or who controls a directory) can install a "skill" from any filesystem location, causing the server to read and index arbitrary SKILL.md files outside the intended skills directories.

## Location

- **Handler**: `dashboard/routes/skills.py:132` -- `POST /api/skills/install`
- **Path construction**: `dashboard/routes/skills.py:135` -- `path = Path(req.path)`
- **Existence check**: `dashboard/routes/skills.py:136-137` -- validates path exists and is a directory (confirms attacker path is accessible)
- **File read**: `dashboard/routes/skills.py:139` -- `skill_md = path / "SKILL.md"` then `parse_skill_md(path)`
- **Auth gate**: `Depends(get_current_user)` present

## Attacker Control

Full control over `req.path` (the `path` field of the JSON request body). Any absolute or relative path accepted.

## Trust Boundary Crossed

Authenticated-session-to-filesystem boundary. Authenticated user reads and indexes files from outside the configured skills directories.

## Impact

- Probe filesystem for directory existence via 400 vs 200 response codes
- If attacker can write a `SKILL.md` to a target directory (e.g., via the MCP write primitive), cause the server to read and return the content of that file via the skill index
- `parse_skill_md` reads and returns the full file content — this content is indexed in the vector store and returned in search results, effectively exfiltrating it
- Confirm presence of sensitive directories (e.g., `~/.ssh`, `/root`, cron directories)

## Evidence

1. `skills.py:135` -- `path = Path(req.path)` — no containment check against SKILLS_DIRS
2. `skills.py:136` -- `if not path.exists() or not path.is_dir()` — confirms arbitrary path resolution
3. `skills.py:139` -- `skill_md = path / "SKILL.md"` — reads from user-supplied path
4. `skills.py:143` -- `data = parse_skill_md(path)` — full file content parsed and indexed
5. Compare with `api_utils.py:330-342` where `is_relative_to` IS used for metadata classification — but NOT for access control

## Reproduction Steps

1. Obtain a valid auth token
2. Identify a target directory with a SKILL.md (or create one via MCP write primitive)
3. Send: `POST /api/skills/install` with body `{"path": "/tmp/attacker-skill"}`
4. If directory and SKILL.md exist, server returns `{"status": "installed", "skill": "..."}` and indexes the content
5. Retrieve indexed content via `GET /api/skills/search?q=...` to exfiltrate
