# Plan: Supervisor Format
 
---
 
# Project: Manager Role Refactoring — CLI-First Subcommand Architecture
 
**Routing tags:** `[ostwin-cli]`, `[roles-infra]`, `[manager-role]`
 
**Objective:** Expose every role's capabilities as first-class CLI subcommands via
`ostwin role <role_name> <subcommand> [--options]`, with layered discovery
(project-local → agent-dir → user-global), project-local override cloning,
and a manager-driven redesign loop for self-healing failed subcommands.
 
**Tech stack:** Bash (ostwin entrypoint), PowerShell 7+ (manager scripts),
Python 3.10+ (role modules, JSON parsing), Pester 5 (tests)
 
**Search path priority (highest → lowest):**
```
$PROJECT_DIR/.ostwin/roles/{role}/    ← project-local overrides
$AGENT_DIR/roles/{role}/              ← installed roles
$HOME/.ostwin/roles/{role}/           ← user-global roles
```
 
---
 
## EPIC-001 — Subcommand Manifest Schema (`subcommands.json`)
**Goal**: Define a declarative manifest format so each role can advertise its
callable entrypoints. Roles without the manifest keep working — zero breaking changes.
 
**Tasks:**
- [ ] `[roles-infra]` Create `subcommands.json` JSON Schema definition under `$AGENT_DIR/schemas/subcommands-schema.json`. Fields: `role` (string, required), `language` (enum: python|powershell|bash|node, required), `module_root` (string, default "."), `subcommands[]` array. Each entry: `name` (string, required), `type` (enum: cli|script|function), `entrypoint` (string, required — e.g. `cli.py::main` or `Start-ManagerLoop.ps1`), `invoke` (string, required — shell template with `{args}` placeholder), `description` (string), `args_schema` (object, optional — `positional[]`, `optional{}`).
- [ ] `[roles-infra]` Write a `validate-subcommands.sh` helper that takes a path to a `subcommands.json` and validates it against the schema using Python's `jsonschema` library. Exit 0 on valid, exit 1 + stderr on invalid. Script location: `$AGENT_DIR/bin/validate-subcommands.sh`.
- [ ] `[roles-infra]` Author the **reporter** role manifest at `$AGENT_DIR/roles/reporter/subcommands.json` with three subcommands: `generate` (invoke: `python -m reporter generate {args}`), `validate` (invoke: `python -m reporter validate {args}`), `list-components` (invoke: `python -m reporter list-components`). Include `args_schema` for `generate` (`positional: ["spec_file"]`, `optional: {"-o|--output": "Output PDF path"}`).
- [ ] `[manager-role]` Author the **manager** role manifest at `$AGENT_DIR/roles/manager/subcommands.json` with three subcommands: `start` (invoke: `pwsh -NoProfile -File Start-ManagerLoop.ps1 {args}`), `triage` (invoke: `pwsh -NoProfile -File Triage-Room.ps1 {args}`), `redesign` (invoke: `pwsh -NoProfile -File Redesign-Subcommand.ps1 {args}`).
- [ ] `[roles-infra]` Add a `subcommands.json` stub template to `$AGENT_DIR/roles/_base/subcommands.json.template` so new roles created by `ostwin init-role` get a skeleton manifest.
 
---
 
## EPIC-002 — `ostwin role` CLI Dispatch Command
**Goal**: Wire the `role)` case into the main `ostwin` bash entrypoint so that
`ostwin role`, `ostwin role <name>`, and `ostwin role <name> <sub> [args...]`
all work end-to-end with layered path resolution.
 
**Tasks:**
- [ ] `[ostwin-cli]` **List all roles** — Add the `role)` case block to the main `case "$1" in` dispatch in the `ostwin` script, placed between the existing `mcp)` and `config)` cases. When `$ROLE_NAME` is empty, iterate over `$AGENTS_DIR/roles`, `$HOME/.ostwin/roles`, and `$(pwd)/.ostwin/roles`. For each directory: skip `_base` and `__pycache__`; if `subcommands.json` exists, count and display subcommand count; otherwise print the role name plain. Deduplicate role names across paths (project-local wins display).
- [ ] `[ostwin-cli]` **Show single role info** — When `$ROLE_NAME` is set but `$SUBCMD` is empty, resolve the role directory using the three-tier search path (project-local → `$AGENTS_DIR` → `$HOME/.ostwin`). Print: role name, resolved path, and if `subcommands.json` exists, a formatted table of subcommand names + descriptions using an inline Python one-liner (`json.load → loop → f-string`).
- [ ] `[ostwin-cli]` **Dispatch subcommand** — When both `$ROLE_NAME` and `$SUBCMD` are set: load `subcommands.json` from the resolved role dir; extract the `invoke` template for the matching subcommand name via inline Python; if not found, print `✗ Unknown subcommand` to stderr and exit 1; otherwise `cd "$ROLE_DIR"`, substitute `{args}` → `"$*"` using `sed`, and `eval` the final command.
- [ ] `[ostwin-cli]` **Update `show_help()`** — Append the following block to the help text output:
  ```
  role <name> [sub]  Run a role's subcommand
                       Options: ostwin role (list roles)
                                ostwin role <name> (show subcommands)
                                ostwin role <name> <sub> [args...]
  ```
- [ ] `[ostwin-cli]` **Edge-case hardening** — Handle: (a) role dir exists but has no `subcommands.json` and no `role.json` → print not found; (b) role dir exists with `role.json` but no `subcommands.json` → show role info but print "no subcommands defined"; (c) `{args}` placeholder missing from `invoke` template → append raw `$*` to end of command; (d) spaces and special characters in arguments → ensure quoting survives the `eval`.
 
---
 
## EPIC-003 — Project-Local Override Cloning (`Clone-RoleToProject.ps1`)
**Goal**: Let users (and the manager) clone any installed role into
`$PROJECT_DIR/.ostwin/roles/{role}/` for local modification without
touching the global installation.
 
**Tasks:**
- [ ] `[roles-infra]` Create `Clone-RoleToProject.ps1` under `$AGENT_DIR/roles/manager/`. Parameters: `-RoleName` (mandatory), `-ProjectDir` (mandatory, defaults to `$PWD`), `-SubcommandFilter` (optional string array — if set, copy only files referenced by those subcommands' `entrypoint` fields plus `subcommands.json` and `role.json`). Logic: (1) resolve source role dir using the same three-tier search; (2) create target at `$ProjectDir/.ostwin/roles/$RoleName/`; (3) `Copy-Item -Recurse` source → target (or filtered files); (4) write `.clone-manifest.json` with fields: `source_path`, `source_sha` (git sha of source dir if in a repo, else file hash), `cloned_at` (ISO 8601 timestamp), `filter` (subcommand names if filtered, else null).
- [ ] `[roles-infra]` Add a `clone` subcommand to the manager's `subcommands.json`: `{ "name": "clone", "type": "script", "entrypoint": "Clone-RoleToProject.ps1", "invoke": "pwsh -NoProfile -File Clone-RoleToProject.ps1 {args}", "description": "Clone a role to project-local for override" }`.
- [ ] `[ostwin-cli]` Add a convenience alias: `ostwin clone-role <role> [--project-dir <path>]` that delegates to `ostwin role manager clone -RoleName <role> -ProjectDir <path>`.
- [ ] `[roles-infra]` Write a `Resolve-RoleDir` shared PowerShell function (in a `SharedUtils.psm1` module) that encapsulates the three-tier path search, so all scripts use one resolution function instead of duplicating the logic.
 
---
 
## EPIC-004 — Error Log Analysis (`Analyze-ErrorLog.ps1`)
**Goal**: Give the manager a structured classifier for war-room failures
so it can decide whether to redesign, retry, or escalate.
 
**Tasks:**
- [ ] `[manager-role]` Create `Analyze-ErrorLog.ps1` under `$AGENT_DIR/roles/manager/`. Parameters: `-RoomDir` (path to the war-room directory), `-RoleName` (the role that failed). Logic: (1) read `$RoomDir/channel.jsonl` for the latest error messages (filter events with `type: error` or `type: failed`); (2) load `$RoomDir/../roles/$RoleName/subcommands.json` (or the role's resolved `subcommands.json`); (3) classify using a decision tree:
  - If error message contains a traceback referencing a file in the role's `entrypoint` list → `subcommand-bug`
  - If error message says "unknown subcommand" or "not implemented" or references a capability not in the manifest → `subcommand-missing`
  - If error message contains "ModuleNotFoundError", "command not found", "pip", "npm" → `environment-error`
  - If error message references input file parsing, JSON decode, or schema validation → `input-error`
  - Fallback → `unknown`
- [ ] `[manager-role]` Output format: JSON to stdout: `{ "classification": "subcommand-bug", "confidence": 0.85, "evidence": "Traceback in cli.py line 42", "subcommand": "generate", "recommended_action": "clone-and-redesign" }`.
- [ ] `[manager-role]` Add `analyze` subcommand to `$AGENT_DIR/roles/manager/subcommands.json`: `{ "name": "analyze", "invoke": "pwsh -NoProfile -File Analyze-ErrorLog.ps1 {args}" }`.
- [ ] `[manager-role]` (Optional/stretch) Add an AI-assisted classification path: if confidence < 0.5 from the regex/heuristic classifier, call an LLM with the error log + subcommands manifest and parse the structured response. Gate behind a `-UseAI` switch and `OSTWIN_AI_ENDPOINT` env var.
 
---
 
## EPIC-005 — Subcommand Redesign Loop (`Redesign-Subcommand.ps1`)
**Goal**: Automate the clone → patch → re-execute cycle so the manager
can self-heal a broken subcommand within a war-room scope.
 
**Tasks:**
- [ ] `[manager-role]` Create `Redesign-Subcommand.ps1` under `$AGENT_DIR/roles/manager/`. Parameters: `-RoomDir`, `-RoleName`, `-SubcommandName`, `-ErrorContext` (string — the raw error text or path to error log). Workflow:
  1. Call `Clone-RoleToProject.ps1 -RoleName $RoleName -ProjectDir "$RoomDir/overrides"` — clones the role into `$RoomDir/overrides/$RoleName/`.
  2. Spawn an engineer agent (shell out to `ostwin agent engineer`) targeting `$RoomDir/overrides/$RoleName/` with a prompt that includes: the error context, the current subcommand's `entrypoint` source code (read from disk), and the `subcommands.json` entry.
  3. After the engineer writes the fix: validate that the patched file is syntactically valid (`python -m py_compile` for Python, `pwsh -Command "Get-Command -Syntax"` for PS1).
  4. If `subcommands.json` was modified by the engineer, re-validate it with `validate-subcommands.sh`.
  5. Re-execute the original war-room task using the overridden role dir.
  6. Post a `subcommand-redesigned` event to the room's `channel.jsonl`: `{ "type": "subcommand-redesigned", "role": "$RoleName", "subcommand": "$SubcommandName", "override_path": "$RoomDir/overrides/$RoleName/", "status": "success|failed" }`.
- [ ] `[manager-role]` Add `redesign` subcommand to the manager manifest (already declared in EPIC-001; verify `invoke` points to `Redesign-Subcommand.ps1`).
- [ ] `[manager-role]` Support standalone invocation: `ostwin role manager redesign --room room-003 --role reporter --subcommand generate`. Parse `--room`, `--role`, `--subcommand` from `{args}` inside the script using `param()`.
 
---
 
## EPIC-006 — Manager Loop Enhancements (Override-Aware Execution)
**Goal**: Modify `Start-ManagerLoop.ps1` and `Start-DynamicRole.ps1` to
be aware of overrides and the new `subcommand-redesign` state.
 
**Tasks:**
- [ ] `[manager-role]` **Enhanced triage in `Start-ManagerLoop.ps1`** — In the `Invoke-ManagerTriage` function: after the existing classification logic, add a check: if the assigned role has a `subcommands.json`, load it and cross-reference the error with subcommand entrypoints. If AI confidence ≥ 0.7, return a `subcommand-failure` classification with the specific subcommand name.
- [ ] `[manager-role]` **New state: `subcommand-redesign`** — Add to the state machine in `Start-ManagerLoop.ps1`: on `subcommand-failure` classification → transition to `subcommand-redesign` state → call `Redesign-Subcommand.ps1` with room context → on success → transition to `engineering` (re-run the task) → on failure → transition to `failed-final`. Add a max-redesign counter (default 2) to prevent infinite redesign loops.
- [ ] `[manager-role]` **Override detection in `Start-ManagerLoop.ps1`** — Before spawning any role, check `$RoomDir/overrides/$RoleName/`. If the directory exists and contains a valid `subcommands.json` or `role.json`, set `$EffectiveRoleDir = "$RoomDir/overrides/$RoleName"` and pass it as the working directory to the role runner.
- [ ] `[manager-role]` **Override detection in `Start-DynamicRole.ps1`** — Before loading the role definition from `$AGENTS_DIR/roles/$baseRole`, check `$RoomDir/overrides/$baseRole/`. If present, set `$roleWorkingDir` to the override path. All subsequent file reads (`role.json`, `subcommands.json`, entrypoint scripts) use this path.
- [ ] `[manager-role]` **State machine documentation** — Update the ASCII state diagram in the manager's `ROLE.md` to include the new `subcommand-redesign` state and its transitions:
  ```
  engineering → failed → [triage] →
    ├─ subcommand-failure → subcommand-redesign → engineering (retry)
    │                                           → failed-final (if max redesigns hit)
    ├─ environment-error  → install-deps → retry
    ├─ input-error        → route-upstream
    └─ unknown            → failed-final
  ```
 
---
 
## EPIC-007 — Config Schema & Metadata Updates
**Goal**: Update `config-schema.json` and `ROLE.md` so the new
capabilities are documented and discoverable.
 
**Tasks:**
- [ ] `[roles-infra]` **`config-schema.json`** — Add an optional `overrides` property to the room config object: `"overrides": { "type": "object", "additionalProperties": { "type": "object", "properties": { "path": { "type": "string" }, "cloned_from": { "type": "string" }, "cloned_at": { "type": "string", "format": "date-time" } } } }`. This tracks which roles have been cloned into a room's override directory.
- [ ] `[manager-role]` **`ROLE.md`** — Add a new section "Subcommand-Aware Self-Healing" documenting: the `subcommand-redesign` state, the error classification taxonomy (subcommand-bug, subcommand-missing, environment-error, input-error), the redesign workflow, and the override search path. Include the CLI examples: `ostwin role manager redesign --room ... --role ... --subcommand ...`.
- [ ] `[roles-infra]` **`CHANGELOG.md`** — Append an entry for this release describing: new `ostwin role` command, `subcommands.json` manifest format, project-local overrides, error classification, and self-healing redesign loop.
 
---
 
## EPIC-008 — Tests & Verification
**Goal**: Comprehensive automated + manual verification of all new
functionality, with zero regressions on existing behavior.
 
**Tasks:**
- [ ] `[roles-infra]` **`SubcommandCLI.Tests.ps1`** — Pester test file covering:
  - `ostwin role` lists all discoverable roles from both `$AGENTS_DIR` and `$HOME/.ostwin`
  - `ostwin role reporter` shows subcommands from the manifest
  - `ostwin role reporter list-components` dispatches correctly (mock the actual command, verify the `eval`'d command string)
  - Project-local override in `$(pwd)/.ostwin/roles/reporter/` takes priority over `$AGENTS_DIR`
  - Role without `subcommands.json` shows info but no subcommand list
  - Unknown subcommand prints error to stderr and exits 1
  - Unknown role name prints error to stderr and exits 1
- [ ] `[roles-infra]` **`CloneRole.Tests.ps1`** — Pester test file covering:
  - `Clone-RoleToProject.ps1` creates correct directory structure under `$ProjectDir/.ostwin/roles/$RoleName/`
  - `.clone-manifest.json` contains valid fields (source_path, cloned_at)
  - `-SubcommandFilter` copies only the files tied to specified subcommands
  - Cloning an already-cloned role overwrites cleanly
- [ ] `[manager-role]` **`ErrorAnalysis.Tests.ps1`** — Pester test file covering:
  - `Analyze-ErrorLog.ps1` returns `subcommand-bug` for a traceback in an entrypoint file
  - Returns `environment-error` for `ModuleNotFoundError`
  - Returns `input-error` for JSON decode errors
  - Returns `subcommand-missing` for "not implemented" messages
  - Output is valid JSON with required fields (classification, confidence, recommended_action)
- [ ] `[manager-role]` **`RedesignLoop.Tests.ps1`** — Pester test file covering:
  - Full lifecycle: engineering → fail → `subcommand-redesign` → re-engineering → pass
  - Max redesign counter prevents infinite loops (default 2, then `failed-final`)
  - `subcommand-redesigned` event is posted to `channel.jsonl`
- [ ] `[roles-infra]` **Regression** — Run existing orchestration tests to confirm no breakage:
  ```bash
  pwsh -Command "Invoke-Pester -Path '.agents/tests/roles/manager/Orchestration.Tests.ps1' -Output Detailed"
  ```
- [ ] `[ostwin-cli]` **Manual smoke tests** (documented in test file as comments):
  ```bash
  # 1. List all roles
  ostwin role
 
  # 2. Show reporter subcommands
  ostwin role reporter
 
  # 3. Run a reporter subcommand
  ostwin role reporter list-components
 
  # 4. Clone reporter to project
  ostwin role manager clone -RoleName reporter -ProjectDir .
 
  # 5. Verify project-local override takes priority
  ostwin role reporter   # should show path = $(pwd)/.ostwin/roles/reporter
 
  # 6. Redesign help
  ostwin role manager redesign --help
  ```
 
---
 
## Dependency Graph
 
```
EPIC-001 (Manifest Schema)
    │
    ├──► EPIC-002 (CLI Dispatch)  ← can start after manifest schema is defined
    │        │
    │        └──► EPIC-008 (Tests — CLI portion)
    │
    ├──► EPIC-003 (Clone Script)  ← needs manifest to know what to clone
    │        │
    │        └──► EPIC-005 (Redesign Loop)  ← calls Clone internally
    │                 │
    │                 └──► EPIC-006 (Manager Loop Enhancements)
    │
    ├──► EPIC-004 (Error Analysis) ← needs manifest to classify subcommand failures
    │        │
    │        └──► EPIC-006 (Manager Loop Enhancements)  ← uses classifier output
    │
    └──► EPIC-007 (Config & Docs)  ← can run in parallel, finalize after EPIC-006
              │
              └──► EPIC-008 (Tests — full integration)
```
 
**Recommended execution order:**
1. EPIC-001 → EPIC-002 (foundation)
2. EPIC-003 + EPIC-004 (parallel, both depend only on EPIC-001)
3. EPIC-005 (depends on EPIC-003 + EPIC-004)
4. EPIC-006 (depends on EPIC-005)
5. EPIC-007 (parallel with EPIC-006, finalize after)
6. EPIC-008 (runs incrementally per EPIC, full suite at end)
 
---
 
## Max Loop Count
Engineer↔QA: 3 cycles per phase. Escalate to Supervisor on cycle 4.
 
## Status: IN_PROGRESS