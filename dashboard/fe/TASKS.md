# Tasks for EPIC-001 — Structured EPIC Markdown Parser & Serializer

- [x] TASK-001 — Define `EpicDocument` AST types and interfaces in `src/lib/epic-parser.ts`
  - AC: All types from the brief are present and correctly typed.
- [x] TASK-002 — Implement `parseEpicMarkdown` core logic
  - AC: Parser handles H1, preamble, EPIC headers, metadata, sections, checklists, tasklists, and depends_on.
- [x] TASK-003 — Implement `serializeEpicMarkdown`
  - AC: Serializer can convert `EpicDocument` back to markdown string using AST fields.
- [x] TASK-004 — Support round-trip fidelity
  - AC: `serialize(parse(markdown)) === markdown` for all existing plan files, AND edited ASTs reflect changes.
- [x] TASK-005 — Implement unit tests with Vitest
  - AC: 100% coverage of parser and serializer, tests for all edge cases and pattern variations.
- [x] TASK-006 — Verify against repo files (`PLAN.md`, `PLAN-GROWTH.md`, `refactor-skills-ui.md`)
  - AC: No differences after round-trip for all files.
- [x] TASK-007 — Final review and documentation
  - AC: Lint clean, no hardcoded secrets, code comments for complex logic.
- [x] TASK-008 — [FIX] Support robust YAML parsing for `depends_on`
  - AC: Handles both inline and multi-line YAML array formats.
- [x] TASK-009 — [FIX] Add tests for AST modification and serialization
  - AC: Tests verify that changing `task.completed` or adding/removing tasks correctly updates the serialized markdown.
