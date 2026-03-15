# TODO: Enhance Manager Role — Maximize Epic Plan Detail

## Action Items

- [x] **EPIC-003: Expand-Plan.ps1 Engine**
    - [x] Create `plan/Expand-Plan.ps1` skeleton
    - [x] Implement markdown parsing for Epics
    - [x] Integrate with `deepagents` CLI for AI refinement
    - [x] Implement file writing for `PLAN.refined.md`
    - [x] **New**: Added "Implementation Strategy" breakdown in AI prompt for team detail
    - [x] Add dry-run support
    - [x] Create `plan/Expand-Plan.Tests.ps1`

- [x] **EPIC-002: Channel-Based Plan Negotiation**
    - [x] Add `plan-review` and `plan-approve` to `Post-Message.ps1` validation
    - [x] Update `channel/Post-Message.ps1`
    - [x] Create integration test for plan negotiation message types

- [x] **EPIC-001: Manager Refinement Phase**
    - [x] Implement logic in `Start-Plan.ps1` to detect underspecified plans
    - [x] Add pre-processing step to manager loop
    - [x] Implement wait-for-approval logic using existing channel scripts

- [x] **EPIC-004: Manager Integration**
    - [x] Update `Start-Plan.ps1` with `-Expand` and `-Review` flags
    - [x] Update `Start-Plan.ps1` logic to invoke `Expand-Plan.ps1`
    - [x] Update logging in manager loop
    - [x] Verify `config.json` integration

## Release Notes

### v0.3.0 — Plan Expansion & Review

**New features:**
- `plan/Expand-Plan.ps1` — AI-driven Epic expansion using the Architect role
- "Implementation Strategy" section required in every expanded Epic
- Channel-based plan review flow (`plan-review`, `plan-approve`, `plan-reject`)
- Auto-expansion of underspecified Epics (< 5 DoD, < 5 AC, < 2 desc bullets) in `Start-Plan.ps1`
- War-room `TaskDescription` now includes full expanded body (Implementation Strategy)
- Global `working_dir` parsed from `PLAN.md` `## Config` section

**Bug fixes (post-review):**
- Aligned well-specified threshold to 5 DoD + 5 AC + 2 bullets in both `Expand-Plan.ps1` and `Start-Plan.ps1`
- `working_dir` parse now emits a `Write-Warning` when path is invalid; silently ignored before
- Removed duplicate "Find end of section" comment in `Expand-Plan.ps1`
- Fixed parameter docs: `.PARAMETER OutputFile` → `.PARAMETER OutFile`; added `$AgentCmd` docs
- Approval loop now times out after 300s (configurable via `PLAN_REVIEW_TIMEOUT_SECONDS`)
- `$Host.UI.RawUI.KeyAvailable` is now guarded with try/catch for non-interactive/CI sessions

### v0.3.0-alpha.1
- Initializing project for Plan Expansion and Manager Refinement.
- Created `TODO.md` to track progress.
