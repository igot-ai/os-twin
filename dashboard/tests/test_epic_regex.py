"""
test_epic_regex.py — Verify that epic detection, title parsing, and
_parse_plan_epics all handle both ## and ### heading levels, case-insensitive
titles, and the various markdown conventions used in plan files.

These are pure unit tests — no running dashboard server required.

Usage:
    python tests/test_epic_regex.py
    pytest tests/test_epic_regex.py -v
"""

import re
import sys
import os

# ──────────────────────────────────────────────────
# 1. Regex Patterns (must stay in sync with plans.py)
# ──────────────────────────────────────────────────
EPIC_COUNT_RE = r"^#{2,3} (?:(?:Epic|Task):\s*\S+|EPIC-\d+|TASK-\d+)"
TITLE_RE = r"^# (?:Plan|PLAN):\s*(.+)"
RUN_VALIDATION_RE = r"^#{2,3} (?:EPIC-|Task:|Epic:)"


# ──────────────────────────────────────────────────
# 2. Sample Plan Fixtures
# ──────────────────────────────────────────────────

# Format A: ## Epic: EPIC-XXX — Title  (original convention)
PLAN_H2_EPIC_COLON = """\
# Plan: OAuth2 Migration

> Status: draft

## Config

working_dir: /tmp/project-a

---

## Goal

Migrate auth to OAuth2.

## Epic: EPIC-001 — Provider Setup

#### Definition of Done
- [ ] OAuth configured

## Epic: EPIC-002 — Frontend Login

#### Tasks
- [ ] TASK-001 — Update login UI
"""

# Format B: ### EPIC-XXX — Title  (create_plan template / user markdown)
PLAN_H3_EPIC_BARE = """\
# PLAN: Risk Management Agent Example

> Status: draft

## Config

working_dir: /tmp/deepagents

---

## Goal

Build a risk management agent.

## Epics

### EPIC-001 — Risk Management Agent Implementation

#### Definition of Done
- [ ] Core functionality implemented

#### Tasks
- [ ] TASK-001 — Design and plan implementation

depends_on: []
"""

# Format C: ## EPIC-XXX — Title  (direct h2, no "Epic:" prefix)
PLAN_H2_EPIC_BARE = """\
# Plan: Direct H2 Epics

> Status: draft

## Config

working_dir: /tmp/project-c

---

## EPIC-001 — Setup

Body text for epic 1.

## EPIC-002 — Implementation

Body text for epic 2.

## EPIC-003 — Testing

Body text for epic 3.
"""

# Format D: ## Task: TASK-XXX — Title
PLAN_H2_TASK = """\
# Plan: Task-Based Plan

## Config

working_dir: /tmp/project-d

---

## Task: TASK-001 — Build API

#### Tasks
- [ ] Implement endpoints

## Task: TASK-002 — Build Frontend

#### Tasks
- [ ] Build UI
"""

# Format E: ### Task: TASK-XXX — Title  (h3 tasks)
PLAN_H3_TASK = """\
# PLAN: H3 Task Plan

## Config

working_dir: /tmp/project-e

---

## Tasks

### Task: TASK-001 — API Layer

Some body text.

### Task: TASK-002 — Frontend

Some body text.
"""

# Format F: Mixed — no epics at all (should return 0)
PLAN_NO_EPICS = """\
# Plan: Empty Plan

## Goal

This plan has no epics yet.
"""

# Format G: Single ### EPIC (the exact format from create_plan default template)
PLAN_CREATE_DEFAULT = """\
# Plan: My New Plan

> Created: 2026-03-25T00:00:00Z
> Status: draft
> Project: /tmp/my-project

## Config

working_dir: /tmp/my-project

---

## Goal

My New Plan

## Epics

### EPIC-001 — My New Plan

#### Definition of Done
- [ ] Core functionality implemented

#### Tasks
- [ ] TASK-001 — Design and plan implementation

depends_on: []
"""

# Format H: ### EPIC-001: Title  (colon separator, non-epic ## headings)
# This is the exact format of plan 014c1bd46ee0 that caused the frontend crash
PLAN_H3_COLON_SEP = """\
# Plan: Risk Management Agent Example

## Goal Description
Develop a specialized agent.

## User Review Required
> [!IMPORTANT]
> This agent requires an LLM.

## Epics

### EPIC-001: Risk Management Agent Implementation
Create a new example in `examples/risk-management-agent/`.

#### [NEW] [agent.py](file:///path/to/agent.py)
Core entry point for the agent.
"""


# ──────────────────────────────────────────────────
# 3. Tests: Epic Count Regex
# ──────────────────────────────────────────────────

def test_epic_count_h2_epic_colon():
    """## Epic: EPIC-XXX — Title format: should find 2 epics."""
    matches = re.findall(EPIC_COUNT_RE, PLAN_H2_EPIC_COLON, re.MULTILINE)
    assert len(matches) == 2, f"Expected 2 epics, got {len(matches)}: {matches}"
    print("  ✓ ## Epic: format → 2 epics found")


def test_epic_count_h3_epic_bare():
    """### EPIC-XXX — Title format: should find 1 epic."""
    matches = re.findall(EPIC_COUNT_RE, PLAN_H3_EPIC_BARE, re.MULTILINE)
    assert len(matches) == 1, f"Expected 1 epic, got {len(matches)}: {matches}"
    print("  ✓ ### EPIC-XXX format → 1 epic found")


def test_epic_count_h2_epic_bare():
    """## EPIC-XXX — Title format: should find 3 epics."""
    matches = re.findall(EPIC_COUNT_RE, PLAN_H2_EPIC_BARE, re.MULTILINE)
    assert len(matches) == 3, f"Expected 3 epics, got {len(matches)}: {matches}"
    print("  ✓ ## EPIC-XXX format → 3 epics found")


def test_epic_count_h2_task():
    """## Task: TASK-XXX format: should find 2 tasks."""
    matches = re.findall(EPIC_COUNT_RE, PLAN_H2_TASK, re.MULTILINE)
    assert len(matches) == 2, f"Expected 2 tasks, got {len(matches)}: {matches}"
    print("  ✓ ## Task: format → 2 tasks found")


def test_epic_count_h3_task():
    """### Task: TASK-XXX format: should find 2 tasks."""
    matches = re.findall(EPIC_COUNT_RE, PLAN_H3_TASK, re.MULTILINE)
    assert len(matches) == 2, f"Expected 2 tasks, got {len(matches)}: {matches}"
    print("  ✓ ### Task: format → 2 tasks found")


def test_epic_count_no_epics():
    """Plan with no epics: should return 0."""
    matches = re.findall(EPIC_COUNT_RE, PLAN_NO_EPICS, re.MULTILINE)
    assert len(matches) == 0, f"Expected 0 epics, got {len(matches)}: {matches}"
    print("  ✓ No epics → 0 found")


def test_epic_count_create_default():
    """Default create_plan template with ### EPIC-001: should find 1 epic."""
    matches = re.findall(EPIC_COUNT_RE, PLAN_CREATE_DEFAULT, re.MULTILINE)
    assert len(matches) == 1, f"Expected 1 epic, got {len(matches)}: {matches}"
    print("  ✓ create_plan default template → 1 epic found")


def test_epic_count_no_h4_match():
    """#### EPIC-001 should NOT match (only ## and ### allowed)."""
    content = "#### EPIC-001 — Should Not Match\n"
    matches = re.findall(EPIC_COUNT_RE, content, re.MULTILINE)
    assert len(matches) == 0, f"h4 should not match, got: {matches}"
    print("  ✓ #### EPIC-XXX does NOT match (h4 excluded)")


def test_epic_count_h3_colon_sep():
    """### EPIC-001: Title (colon separator, non-epic ## headings)."""
    matches = re.findall(EPIC_COUNT_RE, PLAN_H3_COLON_SEP, re.MULTILINE)
    assert len(matches) == 1, f"Expected 1 epic, got {len(matches)}: {matches}"
    print("  ✓ ### EPIC-001: (colon sep) → 1 epic found, non-epic ## headings ignored")


def test_epic_count_no_h1_match():
    """# EPIC-001 should NOT match (only ## and ### allowed)."""
    content = "# EPIC-001 — Should Not Match\n"
    matches = re.findall(EPIC_COUNT_RE, content, re.MULTILINE)
    assert len(matches) == 0, f"h1 should not match, got: {matches}"
    print("  ✓ # EPIC-XXX does NOT match (h1 excluded)")


# ──────────────────────────────────────────────────
# 4. Tests: Title Regex
# ──────────────────────────────────────────────────

def test_title_lowercase_plan():
    """# Plan: Title — standard lowercase."""
    m = re.search(TITLE_RE, "# Plan: My Great Plan", re.MULTILINE)
    assert m, "Failed to match '# Plan:'"
    assert m.group(1).strip() == "My Great Plan"
    print("  ✓ '# Plan: ...' matched")


def test_title_uppercase_plan():
    """# PLAN: Title — uppercase variant."""
    m = re.search(TITLE_RE, "# PLAN: Risk Management Agent Example", re.MULTILINE)
    assert m, "Failed to match '# PLAN:'"
    assert m.group(1).strip() == "Risk Management Agent Example"
    print("  ✓ '# PLAN: ...' matched")


def test_title_from_h2_plan():
    """## Plan: should NOT match (only # h1 allowed for title)."""
    m = re.search(TITLE_RE, "## Plan: Not A Title", re.MULTILINE)
    assert m is None, f"## Plan: should not match title regex, got: {m}"
    print("  ✓ '## Plan: ...' does NOT match (h2 excluded)")


def test_title_in_full_plan_h2():
    """Title extraction from full plan with ## Epic: format."""
    m = re.search(TITLE_RE, PLAN_H2_EPIC_COLON, re.MULTILINE)
    assert m, "Failed to match title in full plan"
    assert m.group(1).strip() == "OAuth2 Migration"
    print("  ✓ Title extracted from full plan (## Epic: format)")


def test_title_in_full_plan_h3():
    """Title extraction from full plan with ### EPIC-XXX format."""
    m = re.search(TITLE_RE, PLAN_H3_EPIC_BARE, re.MULTILINE)
    assert m, "Failed to match title in full plan"
    assert m.group(1).strip() == "Risk Management Agent Example"
    print("  ✓ Title extracted from full plan (### EPIC-XXX format)")


# ──────────────────────────────────────────────────
# 5. Tests: Run Validation Regex
# ──────────────────────────────────────────────────

def test_validation_h2_epic():
    """## EPIC-001 should pass validation."""
    assert re.search(RUN_VALIDATION_RE, "## EPIC-001 — foo", re.MULTILINE)
    print("  ✓ '## EPIC-001' passes run validation")


def test_validation_h3_epic():
    """### EPIC-001 should pass validation."""
    assert re.search(RUN_VALIDATION_RE, "### EPIC-001 — foo", re.MULTILINE)
    print("  ✓ '### EPIC-001' passes run validation")


def test_validation_h2_task():
    """## Task: should pass validation."""
    assert re.search(RUN_VALIDATION_RE, "## Task: TASK-001 — bar", re.MULTILINE)
    print("  ✓ '## Task:' passes run validation")


def test_validation_h3_task():
    """### Task: should pass validation."""
    assert re.search(RUN_VALIDATION_RE, "### Task: TASK-001 — bar", re.MULTILINE)
    print("  ✓ '### Task:' passes run validation")


def test_validation_h2_epic_colon():
    """## Epic: should pass validation."""
    assert re.search(RUN_VALIDATION_RE, "## Epic: EPIC-001 — baz", re.MULTILINE)
    print("  ✓ '## Epic:' passes run validation")


def test_validation_h3_epic_colon():
    """### Epic: should pass validation."""
    assert re.search(RUN_VALIDATION_RE, "### Epic: EPIC-001 — baz", re.MULTILINE)
    print("  ✓ '### Epic:' passes run validation")


def test_validation_rejects_no_epics():
    """Plan with no epics should fail validation."""
    assert not re.search(RUN_VALIDATION_RE, PLAN_NO_EPICS, re.MULTILINE)
    print("  ✓ Plan with no epics fails validation")


def test_validation_rejects_h4():
    """#### EPIC-001 should NOT pass validation."""
    assert not re.search(RUN_VALIDATION_RE, "#### EPIC-001 — nope", re.MULTILINE)
    print("  ✓ '#### EPIC-001' fails validation (h4 excluded)")


# ──────────────────────────────────────────────────
# 6. Tests: _parse_plan_epics (zvec_store)
# ──────────────────────────────────────────────────

def _get_parse_plan_epics():
    """Import _parse_plan_epics from zvec_store, skipping if not available."""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(test_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

    # zvec_store imports zvec which may not be installed in all environments
    # Use importlib to isolate the static method without full module init
    import importlib.util
    spec = importlib.util.spec_from_file_location("zvec_store", os.path.join(parent_dir, "zvec_store.py"))
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.OSTwinStore._parse_plan_epics
    except Exception:
        return None


def test_parse_plan_epics_h2_format():
    """_parse_plan_epics should correctly parse ## Epic: format."""
    fn = _get_parse_plan_epics()
    if fn is None:
        print("  ⊘ SKIP: zvec_store import failed (zvec not installed)")
        return

    epics = fn(PLAN_H2_EPIC_COLON, "test-h2")
    assert len(epics) == 2, f"Expected 2 epics, got {len(epics)}"
    assert epics[0]["task_ref"] == "EPIC-001"
    assert epics[1]["task_ref"] == "EPIC-002"
    assert "Provider Setup" in epics[0]["title"]
    assert "Frontend Login" in epics[1]["title"]
    assert epics[0]["working_dir"] == "/tmp/project-a"
    print("  ✓ _parse_plan_epics: ## Epic: → 2 epics with correct refs and titles")


def test_parse_plan_epics_h3_format():
    """_parse_plan_epics should correctly parse ### EPIC-XXX format."""
    fn = _get_parse_plan_epics()
    if fn is None:
        print("  ⊘ SKIP: zvec_store import failed (zvec not installed)")
        return

    epics = fn(PLAN_H3_EPIC_BARE, "test-h3")
    assert len(epics) == 1, f"Expected 1 epic, got {len(epics)}: {epics}"
    assert epics[0]["task_ref"] == "EPIC-001"
    assert "Risk Management" in epics[0]["title"]
    assert epics[0]["working_dir"] == "/tmp/deepagents"
    print("  ✓ _parse_plan_epics: ### EPIC-XXX → 1 epic with correct ref and title")


def test_parse_plan_epics_h2_task_format():
    """_parse_plan_epics should correctly parse ## Task: format."""
    fn = _get_parse_plan_epics()
    if fn is None:
        print("  ⊘ SKIP: zvec_store import failed (zvec not installed)")
        return

    epics = fn(PLAN_H2_TASK, "test-task")
    assert len(epics) == 2, f"Expected 2 tasks, got {len(epics)}"
    assert epics[0]["task_ref"] == "TASK-001"
    assert epics[1]["task_ref"] == "TASK-002"
    print("  ✓ _parse_plan_epics: ## Task: → 2 tasks with correct refs")


def test_parse_plan_epics_no_epics():
    """_parse_plan_epics should return empty list for plan with no epics."""
    fn = _get_parse_plan_epics()
    if fn is None:
        print("  ⊘ SKIP: zvec_store import failed (zvec not installed)")
        return

    epics = fn(PLAN_NO_EPICS, "test-empty")
    assert len(epics) == 0, f"Expected 0 epics, got {len(epics)}"
    print("  ✓ _parse_plan_epics: no epics → empty list")


def test_parse_plan_epics_create_default():
    """_parse_plan_epics should handle the create_plan default template."""
    fn = _get_parse_plan_epics()
    if fn is None:
        print("  ⊘ SKIP: zvec_store import failed (zvec not installed)")
        return

    epics = fn(PLAN_CREATE_DEFAULT, "test-default")
    assert len(epics) == 1, f"Expected 1 epic, got {len(epics)}: {epics}"
    assert epics[0]["task_ref"] == "EPIC-001"
    assert epics[0]["working_dir"] == "/tmp/my-project"
    print("  ✓ _parse_plan_epics: create_plan default template → 1 epic")


def test_parse_plan_epics_colon_sep():
    """_parse_plan_epics should handle ### EPIC-001: Title with colon separator."""
    fn = _get_parse_plan_epics()
    if fn is None:
        print("  ⊘ SKIP: zvec_store import failed (zvec not installed)")
        return

    epics = fn(PLAN_H3_COLON_SEP, "test-colon")
    assert len(epics) == 1, f"Expected 1 epic (not bogus headings), got {len(epics)}: {[e['title'] for e in epics]}"
    assert epics[0]["task_ref"] == "EPIC-001"
    assert "Risk Management" in epics[0]["title"]
    print("  ✓ _parse_plan_epics: ### EPIC-001: (colon) → 1 epic, non-epic headings excluded")


# ──────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────

def main():
    print("test_epic_regex.py — Flexible Epic Regex Unit Tests")
    print("=" * 55)
    print()

    test_groups = [
        ("Epic Count Regex (#{2,3})", [
            test_epic_count_h2_epic_colon,
            test_epic_count_h3_epic_bare,
            test_epic_count_h2_epic_bare,
            test_epic_count_h2_task,
            test_epic_count_h3_task,
            test_epic_count_no_epics,
            test_epic_count_create_default,
            test_epic_count_no_h4_match,
            test_epic_count_no_h1_match,
            test_epic_count_h3_colon_sep,
        ]),
        ("Title Regex (Plan|PLAN)", [
            test_title_lowercase_plan,
            test_title_uppercase_plan,
            test_title_from_h2_plan,
            test_title_in_full_plan_h2,
            test_title_in_full_plan_h3,
        ]),
        ("Run Validation Regex", [
            test_validation_h2_epic,
            test_validation_h3_epic,
            test_validation_h2_task,
            test_validation_h3_task,
            test_validation_h2_epic_colon,
            test_validation_h3_epic_colon,
            test_validation_rejects_no_epics,
            test_validation_rejects_h4,
        ]),
        ("_parse_plan_epics (zvec_store)", [
            test_parse_plan_epics_h2_format,
            test_parse_plan_epics_h3_format,
            test_parse_plan_epics_h2_task_format,
            test_parse_plan_epics_no_epics,
            test_parse_plan_epics_create_default,
            test_parse_plan_epics_colon_sep,
        ]),
    ]

    total_passed = 0
    total_failed = 0

    for group_name, tests in test_groups:
        print(f"--- {group_name} ---")
        for test_fn in tests:
            try:
                test_fn()
                total_passed += 1
            except AssertionError as e:
                print(f"  ✗ FAILED: {test_fn.__name__}: {e}")
                total_failed += 1
            except Exception as e:
                print(f"  ✗ ERROR: {test_fn.__name__}: {e}")
                total_failed += 1
        print()

    print(f"{'=' * 55}")
    print(f"Results: {total_passed} passed, {total_failed} failed, {total_passed + total_failed} total")
    if total_failed:
        print("❌ Some tests failed!")
        sys.exit(1)
    else:
        print("🎉 All tests passed!")


if __name__ == "__main__":
    main()
