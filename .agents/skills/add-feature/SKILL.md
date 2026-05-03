---
name: add-feature
description: Implement a new Unity feature end-to-end"
tags: [engineer, implementation, feature]

---

# Workflow: Add Vertical Slice Feature
description: Implement a new vertical slice feature following project standards.

## References
- **Architecture**: `.agent/architecture/ARCHITECTURE.md` -- folder structure, class responsibilities, DI guide
- **Templates**: `.agent/templates/` -- C# code templates (see `README.md` for usage)

## Preconditions
- Target namespace and functionality clearly defined.
- `unity-coding` skill read and understood.
- Serena project activated (`mcp_serena_activate_project`).
- `.agent/architecture/ARCHITECTURE.md` reviewed for folder structure and patterns.

## Steps
1. **Scaffold**: Copy relevant templates from `.agent/templates/` into `Assets/Game/Scripts/{Feature}/`.
   - Replace `{Feature}` placeholders with the actual feature name.
   - Select template subset based on complexity (see `.agent/templates/README.md`  Template Selection Guide).
2. **Plan**: Identify the slice boundaries (Logic, Data, UI). Create `implementation_plan.md`.
3. **Subagents**: Dispatch parallel subagents for independent components.
   - **Mandatory Context Bundle**:
     - **Skill**: `../unity-coding/`
     - **Scope**: Absolute paths to new and modified files.
     - **Task**: "Implement [Component Name] following Vertical Slice Architecture."
     - **DoD**: Code compiles and adheres to SOLID principles.
4. **Integration**: Connect components via VContainer in the relevant `LifetimeScope`.
   - Follow DI registration patterns from `.agent/architecture/ARCHITECTURE.md`  3.
5. **Validation**: Run `automation-testing` workflow to ensure zero regressions.
6. **Review**: Dispatch `unity-code-review` subagent on all modified files.

## Output
- Feature fully integrated and passing Quality Gates.
