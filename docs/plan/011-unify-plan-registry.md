# Plan 011: Unify Plan Registry

**Status:** Draft
**Date:** 2026-05-07

---

## Problem

The dashboard shows different plans than `ostwin run` uses. Two separate plan stores exist with no sync between them.

| Store | Location | Who writes | Who reads |
|---|---|---|---|
| Source repo plans | `~/os-twin/.agents/plans/` | Dashboard UI (`POST /api/plans/create`) | Dashboard API (`GET /api/plans`) |
| Global registry | `~/.ostwin/.agents/plans/` | `ostwin run` via `Start-Plan.ps1` | `ostwin` CLI, `install.sh` |

When the dashboard starts with `--project-dir ~/.ostwin`, it resolves `PLANS_DIR` to `~/os-twin/.agents/plans/` (the source repo) because that directory exists. Plans registered by `ostwin run` go to `~/.ostwin/.agents/plans/` — a completely different directory. The dashboard never scans the global store when listing plans.

### Symptoms

- `ostwin run gold-mining.plan.md` → registers plan `d6aff5dcdb4e` in global store → works fine
- Dashboard → shows 5 old plans from the source repo → `d6aff5dcdb4e` missing
- `/plans/d6aff5dcdb4e` → "Plan not found" on dashboard

---

## Root Cause

`dashboard/api_utils.py` line 56-69:

```python
def resolve_plans_dir(project_root, agents_dir):
    project_plans_dir = agents_dir / "plans"
    if project_plans_dir.exists():          # ← ~/os-twin/.agents/plans/ exists!
        return project_plans_dir            # ← uses source repo, not global store
    return Path.home() / ".ostwin" / ".agents" / "plans"
```

The global store is only used as a fallback when the source repo plans dir doesn't exist. But the source repo ALWAYS has `.agents/plans/` (it's tracked in git with template files).

---

## Design

### Single source of truth: `~/.ostwin/.agents/plans/`

The global store is the canonical plan registry. All plan operations read from and write to it. The source repo's `.agents/plans/` is only for development templates.

### Changes

**1. `dashboard/api_utils.py` — always use global store**

```python
PLANS_DIR = Path.home() / ".ostwin" / ".agents" / "plans"
```

No resolution logic. No fallback to source repo. The global store is always used.

**2. `dashboard/routes/plans.py` — `GET /api/plans` scans global store**

Already works once `PLANS_DIR` points to the right place.

**3. `dashboard/routes/plans.py` — `POST /api/plans/create` writes to global store**

The `_resolve_plans_dir_for_write()` already writes to `GLOBAL_PLANS_DIR`. No change needed.

**4. `Start-Plan.ps1` — already writes to global store**

No change needed. It writes to `$agentsDir/plans/` which resolves to `~/.ostwin/.agents/plans/`.

**5. `dashboard/zvec_store.py` — point at global store**

The zvec store's `_plans_dir()` needs to point to the global store, not the source repo.

**6. Clean up source repo plans**

Move the template files and delete stale plans from `~/os-twin/.agents/plans/`. Only `PLAN.template.md` should remain (for `install.sh` seeding).

---

## Files to change

| File | Change |
|---|---|
| `dashboard/api_utils.py` | `PLANS_DIR` always points to `~/.ostwin/.agents/plans/` |
| `dashboard/zvec_store.py` | `_plans_dir()` uses `GLOBAL_PLANS_DIR` |
| `~/os-twin/.agents/plans/` | Remove stale plan files, keep only `PLAN.template.md` |

---

## Verification

```bash
# 1. Register a plan via CLI
ostwin run ~/ostwin-workingdir/gold-mining.plan.md

# 2. Dashboard should show it
curl -s -H "Authorization: Bearer $KEY" http://localhost:3366/api/plans | python3 -c "
import json, sys
for p in json.load(sys.stdin).get('plans', []):
    print(p.get('plan_id', p.get('id')), p.get('title'))
"
# Should include d6aff5dcdb4e  Gold Mining Game

# 3. Plan page should load
curl -s http://localhost:3366/plans/d6aff5dcdb4e  # should NOT return 404
```

---

## Risk

| Risk | Mitigation |
|---|---|
| Old dashboard-created plans disappear | They're in `~/os-twin/.agents/plans/` — copy any needed ones to `~/.ostwin/.agents/plans/` before the change |
| Development workflow breaks | Developers creating test plans via dashboard UI will have them in the global store instead of the source repo. This is actually correct — test plans shouldn't be in git. |
