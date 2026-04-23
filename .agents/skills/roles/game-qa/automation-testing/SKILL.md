---
name: automation-testing
description: Design and implement automated test suites"
tags: [qa, testing, automation]

---

# Workflow: Automation Testing
description: Run and manage Unity EditMode/PlayMode tests with high reliability.

## Preconditions
- Unity Editor is open and responsive.
- Test assemblies correctly configured in the project.

## Steps
1. **Discover**: Find existing tests relevant to the changed area using `mcp_serena_search_for_pattern` (search for `[Test]` or `[UnityTest]`).
2. **Execute**: Run tests using the `mcp_unity-editor_tests-run` tool.
   - **Default**: `testMode: 'EditMode'` for fast iteration.
   - **Integration**: `testMode: 'PlayMode'` for logic requiring frame updates or physics.
3. **Analyze**: Verify all tests in the target namespace/class PASS. Check logs via `mcp_unity-editor_console-get-logs` if failures occur.
4. **Maintain**: If functionality changed, update existing tests or create new ones using the `unity-coding` skill.

## Output
- Verified code correctness with zero failing tests.
