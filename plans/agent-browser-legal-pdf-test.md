# Plan: Agent Browser Legal PDF E2E Test

> Created: 2026-05-04T00:00:00+07:00
> Status: draft

## Config

working_dir: .

---

## Goal

Verify that Ostwin can run a browser automation workflow with the `agent-browser` skill: search a Vietnamese legal decree, open a result, download or save a PDF, keep the file inside the project, and report exact artifact paths.

## Execution Contract

- This is an artifact-only test plan. Do not modify repository source files.
- Use the `agent-browser` skill if available.
- Prefer `agent-browser` CLI commands: `open`, `snapshot -i`, `click @eN`, `fill @eN`, `wait --load networkidle`, `screenshot`, `pdf`, and `close`.
- Use refs from snapshots. Do not use coordinate clicks.
- Do not enable stealth, anti-bot bypass, or `OBSCURA_ARGS`.
- If `agent-browser` is unavailable, record the blocker in `artifacts/browser-run-log.md`; then use the available Playwright MCP or `obscura-browser` MCP only as a diagnostic fallback.
- Keep all downloaded/generated browser artifacts under `artifacts/browser-downloads/`.
- Target decree query: `Nghị định 13/2023/NĐ-CP file PDF`.

## EPIC-001 - Browser Capability Preflight

Roles: engineer, qa
Objective: Confirm browser automation tools are available and prepare a clean artifact directory.
Lifecycle:
```text
pending -> engineer -> qa --+-> passed -> signoff
              ^             |
              +-------------+ (on missing evidence)
```

#### Definition of Done
- [ ] `artifacts/browser-run-log.md` exists.
- [ ] `artifacts/browser-downloads/` exists.
- [ ] Tool availability and selected automation path are recorded.
- [ ] QA verdict for preflight is recorded in `artifacts/qa-verdict.md`.

#### Tasks
- [ ] TASK-001 - Create `artifacts/browser-downloads/`.
- [ ] TASK-002 - Check `agent-browser --version` and record the output.
- [ ] TASK-003 - If needed, run `agent-browser install` and record whether it succeeded.
- [ ] TASK-004 - Confirm that the workflow will not use stealth or anti-bot bypass options.
- [ ] TASK-005 - QA verifies the preflight log is clear enough to reproduce the run.

#### Acceptance Criteria
- `artifacts/browser-run-log.md` includes the exact command used to verify `agent-browser`.
- If `agent-browser` is unavailable, the blocker is explicit and the fallback path is named.
- No artifact path points outside the project.

depends_on: []

## EPIC-002 - Search Legal Decree and Capture Evidence

Roles: engineer, qa
Objective: Use browser automation to search for a Vietnamese decree and capture reproducible evidence before attempting a download.
Lifecycle:
```text
pending -> engineer -> qa --+-> passed -> signoff
              ^             |
              +-------------+ (on missing evidence)
```

#### Definition of Done
- [ ] `artifacts/browser-downloads/search-results.png` exists.
- [ ] `artifacts/browser-downloads/decree-page.png` exists.
- [ ] `artifacts/browser-run-log.md` contains the final page URL and title.
- [ ] QA verdict for navigation/search is recorded.

#### Tasks
- [ ] TASK-001 - Open `https://thuvienphapluat.vn` with `agent-browser open`.
- [ ] TASK-002 - Run `agent-browser snapshot -i` and identify the search input and submit control refs.
- [ ] TASK-003 - Search for `Nghị định 13/2023/NĐ-CP file PDF`.
- [ ] TASK-004 - Re-run `agent-browser snapshot -i` after results load.
- [ ] TASK-005 - Open the most relevant result for `Nghị định 13/2023/NĐ-CP`.
- [ ] TASK-006 - Save screenshots to `artifacts/browser-downloads/search-results.png` and `artifacts/browser-downloads/decree-page.png`.
- [ ] TASK-007 - Record the final URL, page title, and the refs used in `artifacts/browser-run-log.md`.
- [ ] TASK-008 - QA verifies the screenshots and log prove the correct decree page was reached.

#### Acceptance Criteria
- Interactions use snapshot refs like `@e1`, not coordinates.
- Screenshots are non-empty files under `artifacts/browser-downloads/`.
- The run log mentions `Nghị định 13/2023/NĐ-CP`.

depends_on: [EPIC-001]

## EPIC-003 - Download or Save the PDF Artifact

Roles: engineer, qa
Objective: Produce a verified PDF artifact for the legal decree and store it inside the project.
Lifecycle:
```text
pending -> engineer -> qa --+-> passed -> signoff
              ^             |
              +-------------+ (on invalid artifact)
```

#### Definition of Done
- [ ] A PDF exists under `artifacts/browser-downloads/`.
- [ ] `artifacts/browser-downloads/download-metadata.json` exists.
- [ ] `artifacts/browser-run-log.md` records the download method.
- [ ] QA verdict for the PDF artifact is recorded.

#### Tasks
- [ ] TASK-001 - Before clicking any download link, create a timestamp marker.
- [ ] TASK-002 - Click the PDF/download ref if the page exposes one.
- [ ] TASK-003 - Locate only new non-empty PDF files created after the marker and move exactly one into `artifacts/browser-downloads/`.
- [ ] TASK-004 - If no direct PDF download is available, use `agent-browser pdf artifacts/browser-downloads/nghi-dinh-13-2023-nd-cp-page.pdf` to save the current decree page as a PDF.
- [ ] TASK-005 - Verify the selected PDF exists, has non-zero size, and begins with the `%PDF` header when possible.
- [ ] TASK-006 - Write `download-metadata.json` with `source_url`, `artifact_path`, `bytes`, `method`, and `verified_at`.
- [ ] TASK-007 - QA verifies the artifact path is relative and the PDF is readable enough for this test.

#### Acceptance Criteria
- The artifact path starts with `artifacts/browser-downloads/`.
- The run fails explicitly if no PDF can be downloaded or generated.
- The run log does not claim success without a verified file.

depends_on: [EPIC-002]

## EPIC-004 - Final QA Report

Roles: qa
Objective: Produce a concise final report that proves the browser workflow is working or identifies the exact blocker.
Lifecycle:
```text
pending -> qa --+-> passed -> signoff
         ^      |
         +------+ (on missing evidence)
```

#### Definition of Done
- [ ] `artifacts/final-browser-e2e-report.md` exists.
- [ ] Report lists every artifact path created by EPIC-001 to EPIC-003.
- [ ] Report includes a pass/fail verdict.

#### Tasks
- [ ] TASK-001 - Verify all expected artifact files exist.
- [ ] TASK-002 - Confirm the PDF artifact is inside `artifacts/browser-downloads/`.
- [ ] TASK-003 - Confirm no source files were modified by this plan.
- [ ] TASK-004 - Write `artifacts/final-browser-e2e-report.md` with command summary, artifact list, and verdict.

#### Acceptance Criteria
- Final report includes exact relative paths.
- Final verdict is `PASS` only if search evidence and PDF artifact are verified.
- If blocked, the report includes the exact failed command or website behavior.

depends_on: [EPIC-003]
