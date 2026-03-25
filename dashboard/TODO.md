# TODO: Role & Skill Lifecycle Management

## EPIC-001 — Role Lifecycle & Registry Enhancements
- [ ] TASK-001 — Implement `RoleEditorPanel` form validation and backend submission
- [ ] TASK-002 — Add `TestConnectionButton` to the role editor and table
- [ ] TASK-003 — Integrate `/api/roles/{id}/dependencies` into a "Where Used" tab in role details
- [ ] TASK-004 — Add provider icons and model tiers to selection UI

## EPIC-002 — Skill Library: Editor & Semantic Discovery
- [ ] TASK-001 — Create `SkillEditorModal` with markdown editor integration
- [ ] TASK-002 — Wire search to `/api/skills/search` and implement scoring UI
- [ ] TASK-003 — Implement "Sync with Disk" button and progress indicator
- [ ] TASK-004 — Add "Trust Level" and "Author" metadata to skill cards

## EPIC-003 — Contextual Placement
- [ ] TASK-001 — Implement `RoleConfigPanel` within Epic Detail view
- [ ] TASK-002 — Create `EpicSkillsManager` for plan-specific `skill_refs`
- [ ] TASK-003 — Add a "System Prompt Preview" modal for resolution simulation

## EPIC-004 — Dynamic Kanban Architecture (Statuses & Waves)
- [ ] TASK-001 — Implement "Dynamic Column Discovery" for `dag.waves`
- [ ] TASK-002 — Implement "Dual-View Controller" toggle in `KanbanBoard`
- [ ] TASK-003 — Allocate EPICs via `progress.json` room status lookup
- [ ] TASK-004 — Wave View UI polish (Wave headers, progress bar placeholders)

---
## RELEASE NOTES
(Queue your finished tasks here for QA)
