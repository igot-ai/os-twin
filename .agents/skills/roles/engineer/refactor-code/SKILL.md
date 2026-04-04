---
name: refactor-code
description: "Use this skill to safely restructure code -- extract functions, rename, reduce duplication -- while keeping all tests green."
tags: [engineer, refactoring, code-quality]
trust_level: core
---

# refactor-code

## Overview

This skill guides you through safe code refactoring. The key principle: **change structure without changing behavior**. Every refactoring step must keep the test suite green.

## When to Use

- When a task or epic requires code restructuring
- When QA or architect feedback identifies code smells
- When preparing code for a new feature (make the change easy, then make the easy change)
- When reducing duplication identified during review

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Refactored code | Various | Project working directory |
| Updated/new tests | Various | Project test directory |
| Refactoring log | Markdown | Channel `done` message |

## Instructions

### 1. Assess the Scope

Before touching code, identify:
- **What to refactor** -- specific files, functions, or modules
- **Why** -- duplication, complexity, poor naming, tight coupling
- **Risk** -- what could break, what depends on this code
- **Test coverage** -- are there existing tests? If not, write them first

### 2. Write Tests First (If Missing)

> **Rule:** Never refactor code without tests. If coverage is low, write characterization tests first.

Characterization tests capture current behavior:
1. Call the function with various inputs
2. Assert on the actual outputs (even if they seem wrong)
3. These tests protect against unintended behavior changes

### 3. Apply Refactoring Patterns

Common safe refactoring moves:

| Pattern | When | How |
|---------|------|-----|
| **Extract Function** | Long function, repeated logic | Pull logic into a named function, call from original site |
| **Extract Module** | File too large, mixed concerns | Move related functions to a new file, update imports |
| **Rename** | Unclear names | Rename variable/function/class, update all references |
| **Inline** | Unnecessary indirection | Replace a trivial wrapper with its body |
| **Replace Magic Values** | Hardcoded numbers/strings | Extract to named constants |
| **Simplify Conditionals** | Complex if/else chains | Use guard clauses, extract predicate functions |
| **Remove Duplication** | Copy-paste code | Extract shared logic, parameterize differences |

### 4. Refactor in Small Steps

For each refactoring move:
1. Make **one** structural change
2. Run the test suite -- must stay green
3. Commit mentally (or actually) before the next move
4. If tests break, revert and try a smaller step

**Never** combine refactoring with behavior changes in the same step.

### 5. Verify the Refactoring

After all changes:
- [ ] All existing tests pass
- [ ] No new tests needed to fail (behavior unchanged)
- [ ] Code complexity reduced (fewer lines, clearer names, less duplication)
- [ ] Imports and references updated everywhere
- [ ] Code lints cleanly

### 6. Post the Done Report

```markdown
## Refactoring Report -- EPIC/TASK-XXX

### What Was Refactored
<summary of the structural changes>

### Refactoring Moves Applied
1. **Extract Function**: `<old_location>`  `<new_function>()`
2. **Rename**: `<old_name>`  `<new_name>`
3. **Remove Duplication**: merged `<file_a>` and `<file_b>` logic into `<shared>`

### Files Modified
- `path/to/file.py` -- <what changed structurally>

### Test Results
- All tests pass: 
- Behavior changes: None (structure only)
```

## Verification

After refactoring:
1. Full test suite passes with zero failures
2. No behavioral changes -- outputs are identical for the same inputs
3. Code is measurably simpler (fewer lines, lower cyclomatic complexity, better names)
4. All imports and references are updated
