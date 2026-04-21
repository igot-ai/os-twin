---
name: code-refactor
description: Refactor existing Unity C# code for quality
tags: [engineer, refactoring, code-quality]
: core
source: project
---

# Workflow: Code Refactor
description: Safely refactor code using Serena semantic analysis to prevent breakage.

## Preconditions
- Serena project activated (`mcp_serena_activate_project`).
- Clean compilation state.

## Steps
1. **Analyze**: Map the impact of the change.
   - Find all references using `mcp_serena_find_referencing_symbols`.
   - Explore symbol structures with `mcp_serena_get_symbols_overview`.
2. **Plan**: Define the refactor strategy (e.g., "Extract Interface", "Move Method"). Document in `implementation_plan.md`.
3. **Execute**: Use high-level semantic tools:
   - `mcp_serena_rename_symbol` for project-wide renames.
   - `mcp_serena_replace_symbol_body` for target logic updates.
4. **Verify**: Run `validation-and-review` workflow. Ensure no cross-module side effects.

## Output
- Refactored code that maintains all original functionality but improves architecture/readability.
