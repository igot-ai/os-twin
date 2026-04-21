---
name: test-review
description: Review test coverage and quality
tags: [qa, testing, review]

source: project
---

# Workflow: Test Review

**Goal:** Review existing test suite quality — identify coverage gaps, stale tests, and systemic weaknesses — producing a prioritized improvement plan.

**Prerequisites:** Test files in `Assets/Tests/`
**Input:** `Assets/Tests/` + `.output/qa/test-design.md` + story ACs
**Output:** `.output/qa/test-review-{date}.md` — coverage report with scored health and action items

**Reference skills:** `../../skills/qa-knowledge/references/regression-testing.md` + `../../skills/qa-knowledge/references/test-priorities.md`

---

## Step 1 — Inventory Existing Tests

1. Load `../../skills/qa-knowledge/references/regression-testing.md`
2. Load `../../skills/qa-knowledge/references/test-priorities.md`
3. Scan `Assets/Tests/` recursively — list all `.cs` test files
4. For each test file:
   - Count `[Test]` and `[UnityTest]` methods
   - Identify which system they test
   - Note test type: unit / integration / performance
5. Load `.output/qa/test-design.md` if exists — for planned vs. actual comparison

Present: "Found {N} test files with {N} test cases across {N} systems."

---

## Step 2 — Coverage Gap Analysis

Cross-reference tests against all stories in `epics-and-stories.md`:

```markdown
## Coverage Analysis

| Story | ACs | Automated Tests | Coverage | Gap |
|-------|-----|----------------|---------|-----|
| E1-1 | 3 | 3 | 100% | None |
| E1-2 | 2 | 1 | 50% | ⚠️ AC2 missing |
| E2-1 | 4 | 0 | 0% | ❌ No tests |
```

Flag all stories with < 80% AC coverage.

---

## Step 3 — Test Quality Analysis

For each test file, check quality indicators:

**Good patterns:**
- [ ] Tests are independent (no ordering dependency)
- [ ] Descriptive names: `MethodName_Condition_ExpectedResult`
- [ ] Clear Arrange/Act/Assert structure
- [ ] No `Thread.Sleep` — use `yield return` or `await`
- [ ] Mocks/stubs for external dependencies
- [ ] Tests clean up after themselves (`TearDown`)

**Anti-patterns to flag:**
- Tests that always pass (no meaningful assertions)
- Tests that test Unity's own functionality (not your code)
- Tests ordered-dependent on prior test state
- `Assert.IsTrue(true)` or trivial assertions
- Tests with > 50 lines (should be split)
- `Debug.Log` spam in tests

Rate each file: ✅ Good | ⚠️ Needs attention | ❌ Needs rewrite

---

## Step 4 — Regression Risk Matrix

```markdown
## Regression Risk Matrix

| System | Change Frequency | Test Coverage | Risk |
|--------|-----------------|--------------|------|
| {system} | High | 30% | 🔴 Add tests before next sprint |
| {system} | Medium | 80% | 🟡 Monitor |
| {system} | Low | 60% | 🟢 Acceptable |

### Known Regressions (if any)
| Bug | Sprint | Missing Test That Would Have Caught It |
|-----|--------|---------------------------------------|
| {bug} | {when} | {test description} |
```

---

## Step 5 — Action Items

```markdown
## Action Items

### Critical (fix this sprint)
1. **{System} — 0% coverage**
   - Add: `{ClassName}Tests.cs` with {N} test cases
   - Focus: {specific methods}
   - Effort: S/M/L

2. **{Test file} — ordering dependency**
   - Fix: Add `[SetUp]` to reset state before each test

### High Priority (next sprint)
3. **Story E2-1 — AC2 not covered**
   - Add: "Given no lives, When timer expires, Then game over"
   - Location: `{ExistingTestFile}`

### Low Priority (backlog)
4. **Rename test methods to descriptive format**
```

---

## Step 6 — Health Score Report

```markdown
## Test Suite Health Report

**Date:** {date} | **Build:** {version}

| Metric | Score | Target |
|--------|-------|--------|
| AC coverage | {N}% | ≥ 80% |
| P1 story automation | {N}% | 100% |
| No anti-patterns | {N}% | ≥ 90% |
| Regression coverage | {N}% | ≥ 70% |

**Overall: {A/B/C/D} — {Excellent/Good/Needs Improvement/Critical}**
```

---

## Step 7 — Save

1. Create `.output/qa/` if needed.
2. Save to `.output/qa/test-review-{date}.md`.
3. Report: "Health score: {grade}. {N} critical gaps. {N} action items."
4. Suggest: "Run `[qa] test-automate` to generate tests for coverage gaps."
