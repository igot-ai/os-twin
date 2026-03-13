---
name: implement-feature
description: Use this skill to implement new features by understanding requirements, following existing patterns, writing code, and adding tests.
---

# implement-feature

## Trigger
When assigned a `task` message to build new functionality.

## Process

1. **Understand**: Read the task description and acceptance criteria fully
2. **Explore**: Examine existing codebase for patterns, conventions, and reusable code
3. **Plan**: Break the feature into logical steps
4. **Implement**: Write code following existing project patterns
5. **Test**: Write or update tests for the new functionality
6. **Report**: Post `done` message with change summary

## Output Format

When posting `done`, include:
```
## Changes Made
- [file]: [what changed]

## How to Test
- [step-by-step testing instructions]

## Notes
- [any caveats or decisions made]
```

## Quality Gates
- Code compiles/parses without errors
- Tests pass
- Follows existing project conventions
- No hardcoded secrets or credentials
