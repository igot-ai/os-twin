# Skill: Run Tests

## Trigger
When needing to execute and report on project tests during review.

## Process

1. **Discover**: Find the project's test framework and configuration
2. **Execute**: Run the full test suite
3. **Analyze**: Parse test output for passes, failures, and errors
4. **Report**: Provide structured test results

## Common Test Frameworks

| Language | Framework | Command |
|----------|-----------|---------|
| Python   | pytest    | `pytest -v --tb=short` |
| Node.js  | jest      | `npm test` |
| Node.js  | vitest    | `npx vitest run` |
| Go       | go test   | `go test ./...` |
| Rust     | cargo     | `cargo test` |
| Java     | maven     | `mvn test` |

## Output Format

```
## Test Results

**Framework**: [name]
**Command**: [command used]
**Status**: PASS / FAIL

### Summary
- Total: [N]
- Passed: [N]
- Failed: [N]
- Skipped: [N]
- Duration: [time]

### Failures (if any)
1. [test name]: [error message]
   - File: [path:line]
   - Expected: [expected]
   - Got: [actual]
```

## Rules
- Always run tests from the project root
- Report ALL failures, not just the first one
- Include test duration for performance awareness
- If no test framework is found, report that clearly
