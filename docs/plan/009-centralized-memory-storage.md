# Plan 009: Centralized Memory Storage with Plan Hash IDs

**Status:** Draft
**Date:** 2026-05-04
**Depends on:** Plan 007 (HTTP transport), Plan 008 (AI gateway)

---

## Problem

Memory storage is fragmented. 31 `.memory/` directories scattered across project dirs. The URL template uses `{env:PROJECT_DIR}` which can't be resolved in the global opencode.json.

### Why not use filename as namespace

The current Plan 007 uses `?persist_dir={env:PROJECT_DIR}/.memory` and some code uses the plan filename stem (e.g., `gold-mining`) as a namespace. Both are wrong:

| Approach | Problem |
|---|---|
| `persist_dir={env:PROJECT_DIR}/.memory` | `PROJECT_DIR` is not an env var at resolve time — placeholder stays unresolved |
| Filename stem (`gold-mining`) | Two plans can have the same filename. User can rename files. Not a stable ID. |

### What IS unique

The dashboard generates plan IDs via `sha256(title:timestamp)[:12]`:
- `50d1334520e4` — unique 12-char hex
- Stable: doesn't change if the file is renamed or moved
- Already used as the primary key in `.agents/plans/<id>.meta.json`

---

## Design

### Centralized storage keyed by plan hash ID

```
~/.ostwin/memory/                          ← centralized store
├── _global/                               ← default (no plan context)
│   ├── notes/
│   └── vectordb/
├── 50d1334520e4/                          ← plan hash ID (unique, stable)
│   ├── notes/
│   └── vectordb/
└── da26d173d446/                          ← different plan
    ├── notes/
    └── vectordb/

~/ostwin-workingdir/gold-mining/
└── .memory → ~/.ostwin/memory/50d1334520e4/   ← symlink for convenience
```

### URL format

Bare URL in the template, `plan_id` injected at runtime:

```
Template:  http://localhost:3366/api/memory-pool/mcp
Runtime:   http://localhost:3366/api/memory-pool/mcp?plan_id=50d1334520e4
```

No `{env:PROJECT_DIR}`. No `persist_dir`. No filename stems. Just the hash ID.

### How plan_id flows

```
ostwin run gold-mining.plan.md
  │
  ├─ Dashboard registered this plan with id=50d1334520e4
  │  (stored in .agents/plans/50d1334520e4.meta.json)
  │
  ├─ ostwin binary resolves plan file → gets plan_id from meta
  │
  ├─ init.ps1 -PlanId 50d1334520e4
  │    ├─ Creates: ~/.ostwin/memory/50d1334520e4/
  │    ├─ Symlink: project/.memory → ~/.ostwin/memory/50d1334520e4/
  │    └─ Patches opencode.json: ?plan_id=50d1334520e4
  │
  ├─ Agent connects to: /api/memory-pool/mcp?plan_id=50d1334520e4
  │    └─ memory_mcp.py resolves: ~/.ostwin/memory/50d1334520e4/
  │    └─ MemoryPool creates slot at that path
  │
  └─ Notes stored centrally, accessible via project symlink
```

### Symlink benefits

```bash
# Human browsing project dir — works transparently
$ ls ~/ostwin-workingdir/gold-mining/.memory/notes/
architecture/mining/gold-mining-microservices-architecture.md

# Same data, accessed from centralized location
$ ls ~/.ostwin/memory/50d1334520e4/notes/
architecture/mining/gold-mining-microservices-architecture.md

# Legacy stdio mode — MEMORY_PERSIST_DIR=/project/.memory
# Follows symlink → writes to central store
```

---

## Changes

### Phase 1: Clean the URL template

**1.1 `mcp-builtin.json`** — bare URL, no query params:
```json
"memory": {
  "type": "remote",
  "url": "http://localhost:3366/api/memory-pool/mcp"
}
```

**1.2 `~/.ostwin/.agents/mcp/config.json`** — same bare URL.

**1.3 `resolve_opencode.py`** — no `{env:*}` in the URL, resolves cleanly. Remove the `skip_server` workaround from Plan 008.

### Phase 2: Fix init.ps1 plan_id patching + symlink

**2.1** Fix the sed pattern to work with the bare URL:
```powershell
# Strip any existing query params from memory URL, then append plan_id
$opencode = Get-Content $opencodeJson -Raw
$opencode = $opencode -replace '(/api/memory-pool/mcp)[^"]*', "`$1?plan_id=$PlanId"
Set-Content $opencodeJson -Value $opencode
```

**2.2** Create the centralized directory + symlink:
```powershell
$centralDir = Join-Path $env:HOME ".ostwin" "memory" $PlanId
New-Item -ItemType Directory -Path $centralDir -Force | Out-Null

$symlinkPath = Join-Path $ProjectDir ".memory"
if (Test-Path $symlinkPath) {
    # Already exists — if it's a real dir, migrate contents first
    if (-not (Get-Item $symlinkPath).LinkType) {
        Copy-Item "$symlinkPath/*" "$centralDir/" -Recurse -Force
        Remove-Item $symlinkPath -Recurse -Force
    }
}
New-Item -ItemType SymbolicLink -Path $symlinkPath -Target $centralDir -Force | Out-Null
```

Linux fallback in `init.sh`:
```bash
central_dir="$HOME/.ostwin/memory/${PLAN_ID}"
mkdir -p "$central_dir"
symlink_path="$PROJECT_DIR/.memory"
if [ -d "$symlink_path" ] && [ ! -L "$symlink_path" ]; then
    # Migrate existing data
    cp -a "$symlink_path"/* "$central_dir/" 2>/dev/null
    rm -rf "$symlink_path"
fi
ln -sfn "$central_dir" "$symlink_path"
```

### Phase 3: Simplify memory_mcp.py

**3.1** Remove `persist_dir` query param support entirely:
- Delete `_persist_dir_ctx` ContextVar
- Delete the `persist_dir` priority check in `_get_memory_for_plan()`
- `_PlanIdInjectingApp` only extracts `plan_id`

**3.2** Update `_resolve_persist_dir` to use plan hash ID directly:
```python
def _resolve_persist_dir(plan_id: str) -> str:
    """Map plan_id (hash) to centralized memory directory."""
    persist_dir = MEMORY_BASE_DIR / plan_id
    persist_dir.mkdir(parents=True, exist_ok=True)
    return str(persist_dir)
```

No more `memory-` prefix — the plan_id IS the directory name (`50d1334520e4/`, not `memory-50d1334520e4/`).

### Phase 4: Migration script

```bash
#!/bin/bash
# migrate-memory.sh — move per-project .memory/ to centralized store
#
# For each project that has a .memory/ directory:
# 1. Determine the plan_id from the plan registry
# 2. Move contents to ~/.ostwin/memory/<plan_id>/
# 3. Replace .memory/ with a symlink

MEMORY_BASE="$HOME/.ostwin/memory"
mkdir -p "$MEMORY_BASE"

for project_memory in ~/ostwin-workingdir/*/.memory; do
    [ -L "$project_memory" ] && continue  # already a symlink

    project_dir=$(dirname "$project_memory")
    project_name=$(basename "$project_dir")

    # Try to find plan_id from plan registry
    plan_id=""
    for meta in ~/os-twin/.agents/plans/*.meta.json; do
        working_dir=$(python3 -c "import json; print(json.load(open('$meta')).get('working_dir',''))" 2>/dev/null)
        if [ "$working_dir" = "$project_dir" ]; then
            plan_id=$(basename "$meta" .meta.json)
            break
        fi
    done

    # Fallback: use project name as plan_id (not ideal but preserves data)
    [ -z "$plan_id" ] && plan_id="$project_name"

    central_dir="$MEMORY_BASE/$plan_id"
    echo "MIGRATE: $project_memory → $central_dir"

    mkdir -p "$central_dir"
    cp -a "$project_memory"/* "$central_dir/" 2>/dev/null
    rm -rf "$project_memory"
    ln -sfn "$central_dir" "$project_memory"
done
```

---

## Verification

```bash
# 1. Init creates symlink
cd ~/ostwin-workingdir/gold-mining && ostwin init
ls -la .memory
# → .memory → /home/user/.ostwin/memory/50d1334520e4

# 2. opencode.json has plan_id (hash, not filename)
python3 -c "import json; print(json.load(open('.opencode/opencode.json'))['mcp']['memory']['url'])"
# → http://localhost:3366/api/memory-pool/mcp?plan_id=50d1334520e4

# 3. Save via HTTP → stored centrally
curl ... 'http://localhost:3366/api/memory-pool/mcp?plan_id=50d1334520e4' ...
ls ~/.ostwin/memory/50d1334520e4/notes/
# → note files

# 4. Symlink works
ls ~/ostwin-workingdir/gold-mining/.memory/notes/
# → same files

# 5. Two plans named "gold-mining" get different IDs
# plan A: 50d1334520e4, plan B: 7f3a2b1c9d0e → separate memory stores
```

---

## Why hash ID, not filename

| | Filename stem | Plan hash ID |
|---|---|---|
| Uniqueness | Two plans can share a name | SHA256 + timestamp = unique |
| Stability | User can rename the file | Hash never changes |
| Length | Variable, can be long | Always 12 chars |
| Already exists | No — derived from filename | Yes — in `.agents/plans/<id>.meta.json` |
| Example | `gold-mining` | `50d1334520e4` |
| Collision risk | High (common names) | Negligible (4 trillion combinations) |

---

## Files to change

| File | Change |
|---|---|
| `.agents/mcp/mcp-builtin.json` | Bare URL (remove `persist_dir` query param) |
| `.agents/mcp/resolve_opencode.py` | Remove `skip_server` workaround |
| `.agents/init.ps1` | Fix sed pattern for plan_id + create symlink |
| `dashboard/routes/memory_mcp.py` | Remove `persist_dir` support, simplify to `plan_id` only |
| New: `scripts/migrate-memory.sh` | Migration script for existing per-project data |
