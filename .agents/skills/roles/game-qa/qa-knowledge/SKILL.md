---
name: qa-knowledge
description: Unity game testing reference — testing strategies, automation patterns, QA workflows for mobile Unity games
tags: [qa, testing, knowledge, unity]
trust_level: core
source: project
---

# qa-knowledge

**Purpose:** Unity game testing reference knowledge — covering testing strategies, automation patterns, and QA workflows for mobile Unity games.

**When to load:** The `qa` role loads this skill before any testing or review task.

---

## Knowledge Files

Load the relevant reference file based on the current task:

| Task | Reference File |
|------|---------------|
| Unity-specific testing patterns | `references/unity-testing.md` |
| Performance profiling and optimization | `references/performance-testing.md` |
| Automated test writing | `references/qa-automation.md` |
| Regression test planning | `references/regression-testing.md` |
| Test priority decisions | `references/test-priorities.md` |
| Smoke test checklists | `references/smoke-testing.md` |
| Game balance validation | `references/balance-testing.md` |
| Playtesting facilitation | `references/playtesting.md` |
| Save/persistence testing | `references/save-testing.md` |
| Mobile input testing | `references/input-testing.md` |

---

## Quick Reference: Unity Testing Stack

| Tool | Purpose | When to Use |
|------|---------|-------------|
| NUnit | Unit test framework | All EditMode tests |
| Unity Test Runner | Test runner + reporter | All automated tests |
| Unity Profiler | Performance measurement | CPU/GPU/Memory analysis |
| Memory Profiler | Leak detection | Memory snapshots comparison |
| Frame Debugger | Rendering analysis | Draw calls, overdraw |
| Physics Debugger | Collision issues | Physics-heavy gameplay |
| NSubstitute | Mocking library | Unit test isolation |

---

## Unity Quality Gates (Always Check)

1. **60fps non-negotiable** — profile on target device, not in editor
2. **Zero GC in hot path** — use Unity Memory Profiler to verify
3. **Scene builder creates all objects** — verify hierarchy depth and names match spec
4. **All ACs have automated tests** — no story ships without test coverage
5. **Visual regression** — screenshot tests for key screens if layout changes
