# Skill: Code Review

## Trigger
When assigned a `review` message to evaluate engineer's work.

## Process

1. **Read Context**: Understand the original task and acceptance criteria
2. **Review Changes**: Examine all modified/created files
3. **Run Tests**: Execute the project's test suite
4. **Check Requirements**: Verify each acceptance criterion is met
5. **Verdict**: Post `pass` or `fail` with detailed reasoning

## Review Checklist

### Correctness
- [ ] Implementation matches task requirements
- [ ] All acceptance criteria are satisfied
- [ ] Edge cases are handled
- [ ] Error handling is appropriate

### Quality
- [ ] Code follows project conventions
- [ ] No code duplication or unnecessary complexity
- [ ] Functions/methods have clear responsibilities
- [ ] Variable/function names are descriptive

### Safety
- [ ] No hardcoded credentials or secrets
- [ ] Input validation at system boundaries
- [ ] No SQL injection, XSS, or command injection risks
- [ ] Dependencies are from trusted sources

### Testing
- [ ] New code has test coverage
- [ ] All existing tests still pass
- [ ] Tests cover happy path and error cases

## Verdict Format

### PASS
```
VERDICT: PASS

## Summary
[1-2 sentence overall assessment]

## Tests
- [X] All tests pass ([N] tests, [N] assertions)

## Notes
- [any minor non-blocking suggestions]
```

### FAIL
```
VERDICT: FAIL

## Issues Found
1. [CRITICAL/MAJOR/MINOR] [description]
   - Expected: [what should happen]
   - Actual: [what happens]
   - Suggested fix: [how to fix]

## Tests
- [test results]
```
