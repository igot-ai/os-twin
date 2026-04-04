---
name: validation-and-review
description: Validate deliverables against acceptance criteria
tags: [qa, validation, review]
trust_level: core
source: project
---

# Workflow: Quality Gate (Validation & Review)
description: Final verification process before marking any non-trivial task as DONE.

## Preconditions
- Implementation phase complete.
- All temporary scripts deleted.

## Steps
0. **Visual Validation** *(UI tasks only)*: If this task involved building or modifying UI from a reference screenshot, the `add-ui` workflow Step 8 visual checklist **must be completed and all items passed** before proceeding. Do not continue to Step 1 with any open visual precision failures.

1. **Compile**: Verify zero compilation errors in the IDE.
2. **Test**: Run the `automation-testing` workflow. Ensure 100% pass rate for the affected module.
3. **Review**: Execute the `code-review` workflow.
   - **Mandatory**: Fix all **Critical** findings.
   - **Recommended**: Resolve **Warnings** or provide justification.
4. **Walkthrough**: Create a `walkthrough.md` documenting the changes, tests run, and final state (including screenshots for UI changes).

## Output
- Verified, reviewed, and documented code ready for user delivery.

