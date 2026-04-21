---
name: code-review
description: Review Unity C# code for quality and correctness"
tags: [qa, review, code-quality]
: core
---

# Workflow: Code Review Gate
description: Mandatory quality check for all C# changes in the game or editor folders.

## Preconditions
- Code compiles without errors.
- Tests (if applicable) have been run.

## Steps
1. **Inventory**: Identify all added/modified C# files in `Assets/Game/` or `Assets/Editor/`.
2. **Dispatch**: Trigger the `unity-code-review` subagent.
   - **Context Bundle**:
     - **Skill**: `.agent/skills/unity-code-review/`
     - **Scope**: List of all changed file paths.
     - **Output**: `.agent/reviews/[FeatureName]-[YYYY-MM-DD].md`
3. **Evaluate**: Read the generated report. 
   - **CRITICAL**: Must be fixed immediately.
   - **WARNING**: Must be addressed or explicitly justified as a known exception.
4. **Finalize**: Task is DONE only when zero Critical findings remain.

## Output
- Approved code review report in `.agent/reviews/`.
