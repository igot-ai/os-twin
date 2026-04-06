# Plan: Epic Asset Architecture — Master Agent Communication & Asset Management

> Created: 2026-04-06T10:00:00Z
> Status: draft
> Project: /Users/thangtiennguyen/Documents/Cursor/project/igotai/os-twin

## Config

working_dir: /Users/thangtiennguyen/Documents/Cursor/project/igotai/os-twin

---

## Goal

Build a complete asset management architecture so the master agent can communicate with the user during plan creation, collect assets (files, images, specs, data), bind them to specific epics, and inject them into war rooms at execution time. Today assets live only at the plan level with no epic-level binding, no guided collection flow, and no injection into the agent runtime. This plan closes those gaps end-to-end: data model, API, bot conversation flow, manager injection, and dashboard UI.

## Epics

### EPIC-001 — Asset Data Model & Storage Layer
**Phase:** 1
**Priority:** P0
**Owner:** engineer

Objective: Extend the file-based data model to support per-epic asset binding with metadata, tags, and type classification.
Skills: python, fastapi, file-io, pydantic

#### Description
Currently `meta.json` stores a flat `assets[]` array at the plan level. We need to add an `epic_assets` mapping that links assets to specific epics, with optional tags and type classification (design-mockup, api-spec, test-data, reference-doc, config, media). The storage layer should support both plan-level assets (shared across all epics) and epic-scoped assets. Asset records gain new fields: `bound_epics[]`, `asset_type`, `tags[]`, and `description`.

#### Definition of Done
- [ ] `meta.json` schema extended with `epic_assets: { "EPIC-NNN": ["asset-filename", ...] }` mapping
- [ ] Asset records include `bound_epics`, `asset_type`, `tags`, and `description` fields
- [ ] Backward-compatible: existing plans with flat `assets[]` still work without migration
- [ ] Helper functions for binding/unbinding assets to epics

#### Acceptance Criteria
- [ ] `_normalize_plan_assets()` populates new fields with defaults for legacy assets
- [ ] `bind_asset_to_epic(plan_id, filename, epic_ref)` and `unbind_asset_from_epic()` work correctly
- [ ] Assets not bound to any epic are treated as plan-level (available to all epics)
- [ ] Unit tests cover legacy migration, binding, unbinding, and listing per-epic

#### Tasks
- [ ] TASK-001 — Extend asset dict schema in `dashboard/routes/plans.py`
  Add `bound_epics: list[str]`, `asset_type: str`, `tags: list[str]`, `description: str` to asset records. Update `_default_meta()`, `_normalize_plan_assets()`, and `_serialize_plan_asset()`.
- [ ] TASK-002 — Add `epic_assets` mapping to meta.json
  Add `epic_assets` top-level key to meta. Write `_sync_epic_assets_index()` to rebuild the mapping from individual asset `bound_epics` arrays.
- [ ] TASK-003 — Create bind/unbind helper functions
  `bind_asset_to_epic(plan_id, filename, epic_ref)` — adds epic to asset's `bound_epics` and updates `epic_assets` index. `unbind_asset_from_epic()` — inverse. `get_assets_for_epic(plan_id, epic_ref)` — returns plan-level + epic-bound assets.
- [ ] TASK-004 — Write unit tests for asset model layer
  Cover: legacy plans without new fields, binding, unbinding, listing per-epic, edge cases (bind to non-existent epic ref).

depends_on: []

---

### EPIC-002 — Asset Management API Endpoints
**Phase:** 1
**Priority:** P0
**Owner:** engineer

Objective: Expose REST endpoints for binding assets to epics, classifying assets, and querying per-epic asset lists.
Skills: python, fastapi, rest-api

#### Description
Extend `dashboard/routes/plans.py` with new endpoints for the asset lifecycle: bind/unbind assets to epics, update asset metadata (type, tags, description), list assets filtered by epic, and bulk-bind during upload. The existing `POST /api/plans/{plan_id}/assets` upload endpoint gains optional `epic_ref`, `asset_type`, and `tags` form fields.

#### Definition of Done
- [ ] New endpoints: bind, unbind, update-metadata, list-by-epic
- [ ] Upload endpoint accepts optional epic binding fields
- [ ] All endpoints follow existing auth pattern (`Depends(get_current_user)`)
- [ ] OpenAPI docs auto-generated

#### Acceptance Criteria
- [ ] `POST /api/plans/{plan_id}/assets` with `epic_ref=EPIC-001` creates asset bound to that epic
- [ ] `POST /api/plans/{plan_id}/assets/{filename}/bind` with `{"epic_ref": "EPIC-002"}` binds existing asset
- [ ] `GET /api/plans/{plan_id}/epics/{epic_ref}/assets` returns combined plan-level + epic-bound assets
- [ ] `PATCH /api/plans/{plan_id}/assets/{filename}` updates type, tags, description
- [ ] Error 404 for non-existent plan, asset, or epic ref

#### Tasks
- [ ] TASK-001 — Add epic binding fields to upload endpoint
  Extend `upload_plan_assets()` with optional Form fields: `epic_ref`, `asset_type`, `tags` (comma-separated). Call `bind_asset_to_epic()` after save.
- [ ] TASK-002 — Create bind/unbind API endpoints
  `POST /api/plans/{plan_id}/assets/{filename}/bind` — body: `{"epic_ref": "EPIC-NNN"}`. `DELETE /api/plans/{plan_id}/assets/{filename}/bind/{epic_ref}` — unbind.
- [ ] TASK-003 — Create per-epic asset listing endpoint
  `GET /api/plans/{plan_id}/epics/{epic_ref}/assets` — returns merged list of unbound (plan-level) + specifically bound assets, with `binding: "plan" | "epic"` field.
- [ ] TASK-004 — Create asset metadata update endpoint
  `PATCH /api/plans/{plan_id}/assets/{filename}` — body: `{"asset_type": "...", "tags": [...], "description": "..."}`.
- [ ] TASK-005 — Integration tests for all new endpoints
  Test upload-with-binding, bind, unbind, list-by-epic, metadata update, error cases.

depends_on: [EPIC-001]

---

### EPIC-003 — Master Agent Conversational Asset Collection
**Phase:** 2
**Priority:** P0
**Owner:** engineer

Objective: Enable the master agent to guide users through asset collection during plan creation via bot conversations (Discord/Telegram).
Skills: typescript, discord.js, telegram-api, conversational-ux

#### Description
When a user creates or refines a plan via the bot (`/draft`, `/edit`, or thread conversation), the master agent should:
1. Analyze the plan's epics and identify which ones would benefit from assets (e.g., "EPIC-002 mentions a design — do you have mockups?")
2. Prompt the user to upload files directly in the chat
3. Accept uploaded files (images, documents, zips) and route them to the dashboard upload API with the correct epic binding
4. Confirm what was received and suggest what else might be needed

This builds on the existing `planning_thread_store.py` conversation system and the bot's file-handling capabilities. The Telegram poller already supports document uploads; Discord supports attachments.

#### Definition of Done
- [ ] Bot detects file attachments in plan-related conversations and uploads them as plan assets
- [ ] Bot prompts user for assets based on epic analysis during `/draft` and `/edit` flows
- [ ] Uploaded files are auto-bound to the relevant epic when context is clear
- [ ] Works on both Discord and Telegram

#### Acceptance Criteria
- [ ] User sends a file while in a plan conversation → file uploaded as asset with correct plan_id
- [ ] If user is discussing a specific epic, asset is auto-bound to that epic
- [ ] Bot sends confirmation: "Saved `design.png` as a design-mockup for EPIC-002"
- [ ] `/draft` flow includes an asset collection step: "Do you have any files to attach?"
- [ ] Telegram document uploads handled via `telegram_poller.py`

#### Tasks
- [ ] TASK-001 — Add file attachment detection to bot command handler
  In `bot/src/commands.ts`, detect `message.attachments` (Discord) during plan conversations. Download and forward to `POST /api/plans/{plan_id}/assets` with epic context.
- [ ] TASK-002 — Add asset upload support to Telegram poller
  In `dashboard/telegram_poller.py`, handle `document` and `photo` message types during planning sessions. Download via Telegram API, upload to plan assets endpoint.
- [ ] TASK-003 — Add asset prompt step to `/draft` flow
  After plan refinement, add a step: "This plan has N epics. Would you like to attach any files? You can upload them now or add later with `/assets`." Track conversation state to route subsequent uploads.
- [ ] TASK-004 — Implement epic-context detection for auto-binding
  When user uploads a file while discussing a specific epic (detected from conversation context or inline menu), auto-set `epic_ref`. Use the plan refinement AI to suggest `asset_type` from the filename and mime type.
- [ ] TASK-005 — Add asset context to plan refinement prompts
  Extend `RefinePlanRequest.asset_context` to include per-epic binding info. When the AI refines a plan, it should reference which assets are available for each epic.

depends_on: [EPIC-002]

---

### EPIC-004 — Asset Injection into War Rooms
**Phase:** 2
**Priority:** P0
**Owner:** engineer

Objective: When an epic's war room starts, automatically inject relevant assets into the room context so agents can use them.
Skills: python, bash, file-management

#### Description
When the manager spawns a war room for an epic, the system should:
1. Resolve the asset set: plan-level assets + epic-bound assets (from `get_assets_for_epic()`)
2. Copy or symlink assets into the room's `artifacts/` directory (or a new `assets/` subdirectory)
3. Inject an asset manifest into the room's `TASKS.md` or system prompt so the engineer/QA agents know what files are available and where
4. Update `_update_plan_assets_section()` to write per-epic asset blocks into the plan markdown

This ensures agents operating in war rooms have immediate access to reference designs, specs, test data, and configs without the user having to manually place files.

#### Definition of Done
- [ ] War room creation copies/symlinks relevant assets into room directory
- [ ] Room's task prompt includes asset manifest with file paths and descriptions
- [ ] Asset manifest is readable by engineer and QA agents
- [ ] System handles missing/deleted assets gracefully

#### Acceptance Criteria
- [ ] Room directory contains `assets/` subdirectory with relevant files after spawn
- [ ] `TASKS.md` includes `## Available Assets` section listing each file with its type and description
- [ ] Engineer agent's system prompt references the asset manifest
- [ ] If an asset file is missing on disk, it's logged as a warning but doesn't block room creation
- [ ] Assets are read-only in the room (copies, not moves)

#### Tasks
- [ ] TASK-001 — Add asset resolution to room spawn logic
  In the manager's room creation flow (`.agents/roles/manager/`), call `get_assets_for_epic()` API or read meta.json directly. Build list of files to inject.
- [ ] TASK-002 — Copy assets into war room directory
  Create `{room_dir}/assets/` and copy resolved files there. Use symlinks for large files (>10MB) to save disk space. Handle missing files with warnings.
- [ ] TASK-003 — Generate asset manifest in TASKS.md
  Append `## Available Assets` section to the room's TASKS.md with a table: filename, type, description, path. This is what the agent reads to know what's available.
- [ ] TASK-004 — Inject asset context into agent system prompts
  Extend `EpicSkillsManager.generate_system_prompt()` in `dashboard/epic_manager.py` to include asset references when assets are present for the epic.
- [ ] TASK-005 — Test asset injection end-to-end
  Create a plan with assets bound to an epic, run it, verify the room gets the assets and the agent prompt references them.

depends_on: [EPIC-001, EPIC-002]

---

### EPIC-005 — Bot Asset Management Commands
**Phase:** 2
**Priority:** P1
**Owner:** engineer

Objective: Extend the bot's `/assets` command to support per-epic views, binding, and inline upload with classification.
Skills: typescript, discord.js, telegram-api

#### Description
Enhance the existing `/assets` command in `bot/src/commands.ts` to:
1. Show assets grouped by epic (not just a flat list)
2. Allow binding/unbinding via inline buttons: "Bind to EPIC-002" / "Unbind"
3. Support asset type selection via dropdown/buttons after upload
4. Show which epics have no assets as a prompt for the user

Also extend the `bot/src/api.ts` client with the new API endpoints from EPIC-002.

#### Definition of Done
- [ ] `/assets` displays grouped-by-epic view with plan-level assets shown separately
- [ ] Inline buttons for bind/unbind to epics
- [ ] Asset type selector after upload
- [ ] API client updated with new endpoints

#### Acceptance Criteria
- [ ] `/assets` with a plan shows: "Plan-level: 2 files | EPIC-001: 1 file | EPIC-002: 3 files | EPIC-003: no assets"
- [ ] User can tap "Bind to..." button → select epic from list → asset bound
- [ ] After uploading a file, bot asks "What type? [Design Mockup] [API Spec] [Test Data] [Reference Doc] [Config] [Other]"
- [ ] Works on both Discord (buttons) and Telegram (inline keyboards)

#### Tasks
- [ ] TASK-001 — Update API client with new endpoints
  Add `bindAsset()`, `unbindAsset()`, `getEpicAssets()`, `updateAssetMetadata()` to `bot/src/api.ts`.
- [ ] TASK-002 — Refactor `/assets` command for grouped view
  Fetch assets, group by `bound_epics` (unbound = "Plan-level"). Show counts per epic. List details when user selects an epic.
- [ ] TASK-003 — Add bind/unbind inline buttons
  Each asset in the detail view gets a "Bind to..." button that shows epic picker, and a "Unbind" button if already bound.
- [ ] TASK-004 — Add asset type selector after upload
  After successful upload, send a follow-up message with type classification buttons. On selection, call `updateAssetMetadata()`.
- [ ] TASK-005 — Test bot commands on Discord and Telegram
  Manual verification of all flows on both platforms.

depends_on: [EPIC-002, EPIC-003]

---

### EPIC-006 — Plan Markdown Asset Sections (Per-Epic)
**Phase:** 3
**Priority:** P1
**Owner:** engineer

Objective: Update the plan markdown writer to include per-epic asset sections so the plan document is self-contained and human-readable.
Skills: python, markdown, regex

#### Description
Currently `_update_plan_assets_section()` writes a single `## Assets` block at the plan level. Extend this to also write asset sub-sections within each epic block, so when you read the PLAN.md you can see exactly which assets each epic has. Each epic should get an `#### Assets` heading (placed after Tasks and before depends_on) containing bullet lines in the format: `- filename (asset-type, mime/type) — description` with a `Path:` sub-line pointing to the absolute file path. The parser must also be updated to read these sections back when loading a plan.

#### Definition of Done
- [ ] Plan markdown includes per-epic `#### Assets` sections
- [ ] Plan-level `## Assets` section still exists for unbound assets
- [ ] Parser can read per-epic asset sections and reconstruct bindings
- [ ] Round-trip: write → read → write produces identical output

#### Acceptance Criteria
- [ ] After binding an asset to EPIC-002, the plan markdown shows it under EPIC-002's `#### Assets`
- [ ] Removing all epic bindings moves the asset back to the plan-level `## Assets` section
- [ ] Plan parser in `plans.py` extracts per-epic assets during plan load
- [ ] No asset info is lost during plan editing/refinement cycles

#### Tasks
- [ ] TASK-001 — Write per-epic asset sections in plan markdown
  Extend `_update_plan_assets_section()` to also insert `#### Assets` blocks within each epic. Place after `#### Tasks` and before `depends_on:`.
- [ ] TASK-002 — Update plan parser to read per-epic asset sections
  Add regex pattern for `#### Assets` within epic blocks. Extract asset entries and populate `bound_epics` in meta.
- [ ] TASK-003 — Handle asset section during plan refinement
  Ensure the AI refinement prompt explicitly instructs the model to preserve `#### Assets` sections and doesn't strip them, or re-inject them programmatically after the AI completes its generation.
- [ ] TASK-004 — Round-trip tests
  Write plan with per-epic assets → parse → re-write → compare. Verify no data loss.

depends_on: [EPIC-001, EPIC-004]

---

### EPIC-007 — Dashboard UI for Asset Management
**Phase:** 3
**Priority:** P2
**Owner:** frontend-engineer

Objective: Add asset management UI to the web dashboard with drag-and-drop upload, epic binding, and visual asset browser.
Skills: html, css, javascript, fastapi-templates

#### Description
The dashboard frontend should provide:
1. An asset panel on the plan detail page showing all assets with thumbnails/icons
2. Drag-and-drop upload zone that auto-detects which epic the user is viewing
3. Asset binding UI: drag an asset onto an epic card, or use a dropdown to assign
4. Asset type badges and tag display
5. Preview for images and text files; download button for all types

This depends on the API endpoints from EPIC-002 being available.

#### Definition of Done
- [ ] Plan detail page has an asset management panel
- [ ] Drag-and-drop upload works with epic context
- [ ] Assets display with type icons and tags
- [ ] Image/text preview inline

#### Acceptance Criteria
- [ ] User can drag a file onto the plan page → uploaded with correct epic binding
- [ ] Asset list shows grouped by epic with plan-level section
- [ ] Clicking an image asset shows a preview
- [ ] User can change asset type and tags via inline editor
- [ ] Works in Chrome and Firefox

#### Tasks
- [ ] TASK-001 — Add asset panel component to plan detail page
  Create asset sidebar or section on the plan view page. Fetch assets from API on load.
- [ ] TASK-002 — Implement drag-and-drop upload
  Use HTML5 drag-and-drop API. Detect which epic section the drop occurred in. Upload with `epic_ref`.
- [ ] TASK-003 — Asset type and tag editor
  Inline editing for asset type (dropdown) and tags (chip input). Call `PATCH` endpoint on change.
- [ ] TASK-004 — Image and text file preview
  Show inline preview for image/* and text/* mime types. Download button for all.
- [ ] TASK-005 — Responsive layout and cross-browser testing
  Ensure layout works on different screen sizes. Test Chrome and Firefox.

depends_on: [EPIC-002, EPIC-005]

---

## Open Questions (Resolved)

> **Q1: Asset size limits?** — **No limit.** No per-file or per-plan size cap. Users are trusted to manage their own storage.

> **Q2: Asset versioning?** — **Replace.** Re-uploading a file with the same name overwrites the previous version. No version history kept. Current behavior is correct.

> **Q3: Asset types — fixed enum or freeform?** — **Freeform with suggested defaults.** The system provides a suggested set (`design-mockup`, `api-spec`, `test-data`, `reference-doc`, `config`, `media`, `other`) as quick-pick options in the bot/UI, but `asset_type` is a freeform string field — users can type any custom label. This keeps the UX guided without being restrictive.

> **Q4: Large binary assets in git?** — **Gitignore assets, track metadata only.** Add `**/assets/` to `.gitignore` within `.agents/plans/` and `.war-rooms/` directories. The `meta.json` manifest (which is small JSON) stays tracked so the asset inventory is versioned even if the binary blobs aren't. Users who want full binary tracking can opt in via Git LFS on their own.

## Verification Plan

### Automated Tests
```bash
# Unit tests for asset model layer
cd dashboard && python -m pytest tests/test_asset_model.py -v

# API integration tests
cd dashboard && python -m pytest tests/test_asset_api.py -v

# Bot command tests
cd bot && npm test -- --grep "assets"

# Round-trip plan parsing tests
cd dashboard && python -m pytest tests/test_plan_roundtrip.py -v
```

### Manual Verification
1. Create a new plan via `/draft` in Discord
2. Upload 3 files during the conversation — verify they appear in `/assets`
3. Bind 2 files to specific epics via inline buttons
4. Run the plan — verify war rooms contain the correct assets in their `assets/` directories
5. Check agent prompts reference the asset manifest
6. View plan in dashboard — verify asset panel shows grouped-by-epic view
7. Edit plan markdown — verify `#### Assets` sections are present per-epic
8. Re-parse edited plan — verify no asset data lost
