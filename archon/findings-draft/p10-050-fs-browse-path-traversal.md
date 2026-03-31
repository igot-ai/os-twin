Phase: 10
Sequence: 050
Slug: fs-browse-path-traversal
Verdict: VALID
Rationale: The /api/fs/browse endpoint accepts an arbitrary path query parameter and lists any directory on the filesystem without any containment check, allowing any authenticated user to enumerate the entire filesystem tree.
Severity-Original: MEDIUM
PoC-Status: pending
Origin-Finding: security/findings-draft/p8-025-fe-catch-all-path-traversal.md
Origin-Pattern: AP-025

## Summary

The `browse_filesystem` handler (`dashboard/routes/system.py:273-295`) accepts a `path` query parameter and calls `Path(path).expanduser().resolve()` followed by `target.iterdir()`. No containment check (e.g., `is_relative_to`) restricts the supplied path to a project root or any baseline directory. Any authenticated user can enumerate arbitrary directories on the server filesystem, including `/etc/`, `/root/`, `~/.ssh/`, `~/.ostwin/`, etc.

## Location

- **Handler**: `dashboard/routes/system.py:273` -- `GET /api/fs/browse`
- **Path construction**: `dashboard/routes/system.py:277` -- `target = Path(path).expanduser().resolve()`
- **Directory listing**: `dashboard/routes/system.py:282` -- `for entry in sorted(target.iterdir())`
- **Auth gate**: `Depends(get_current_user)` present — requires a valid session token

## Attacker Control

Full control over the `path` query parameter. Any absolute or relative path accepted. The `expanduser()` call additionally expands `~` — meaning `~` can be used to probe the home directory of whichever user runs the server process.

## Trust Boundary Crossed

Authenticated-session-to-filesystem boundary. An authenticated user (including an attacker who has obtained a valid session via the DEBUG backdoor, AP-003, or any other auth bypass) can read the full directory tree of the server.

## Impact

- Enumerate every non-dot directory from `/` to find sensitive locations
- Discover: SSH key paths, `.ostwin/.env`, project secrets, deployment credentials
- Combine with fe-catch-all path traversal (p8-025) or other file-read primitives to exfiltrate any discovered file
- Even without a secondary read primitive, directory enumeration reveals installed software, user accounts, cron directories, and config file locations
- Note: hidden files (starting with `.`) are skipped in the listing, but the target directory itself is revealed

## Evidence

1. `system.py:277` -- `target = Path(path).expanduser().resolve()` — user-supplied, no restriction
2. `system.py:278` -- only validates `target.exists() and target.is_dir()` — confirms traversal works
3. `system.py:282` -- `target.iterdir()` — lists all non-hidden entries and returns them in JSON
4. No `is_relative_to()`, no prefix allowlist, no path jail at any point
5. Route registered at `app.include_router(system.router)` with prefix `/api` — reachable at `/api/fs/browse`

## Reproduction Steps

1. Obtain a valid auth token (DEBUG key "DEBUG", or real credentials)
2. Send: `GET /api/fs/browse?path=/etc HTTP/1.1` with `Authorization: Bearer <token>`
3. Observe JSON response listing all non-hidden directories under `/etc`
4. Send: `GET /api/fs/browse?path=~/.ostwin` to enumerate the secrets directory
5. Chain with `GET /%2e%2e/%2e%2e/home/<user>/.ostwin/.env` (p8-025) to read the env file
