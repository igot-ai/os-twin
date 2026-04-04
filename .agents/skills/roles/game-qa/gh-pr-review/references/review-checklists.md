# Review Checklists

Technology-agnostic checklists to run before Unity-specific analysis. Quick pass — flag anything that fails.

## 🔒 Security

- [ ] No secrets, API keys, tokens, or passwords in code or comments
- [ ] No hardcoded credentials or connection strings
- [ ] Input validation on user-facing data (no injection vectors)
- [ ] Sensitive data not logged or exposed in error messages
- [ ] File paths are sanitized (no path traversal)

## ✅ Correctness

- [ ] Logic handles edge cases (null, empty, boundary values)
- [ ] State transitions are valid (no impossible states)
- [ ] API contracts match between caller and callee
- [ ] Return values are checked (no ignored results)
- [ ] Error handling is present and appropriate
- [ ] Race conditions considered in async code
- [ ] Off-by-one errors checked in loops/indices

## 🧪 Testing

- [ ] New logic has corresponding tests (or is clearly covered by existing tests)
- [ ] Tests cover both happy path and error cases
- [ ] Test names describe what they verify
- [ ] No test code in production files
- [ ] Mocks/stubs are appropriate (not over-mocking)

## 🧹 Code Quality

- [ ] No duplicated code (DRY)
- [ ] Functions/methods have single responsibility
- [ ] Naming is clear and consistent
- [ ] No dead code, commented-out blocks, or unused imports
- [ ] Magic numbers are extracted to named constants
- [ ] Code is readable without excessive comments

## ⚡ Performance

- [ ] No allocations in hot paths (Update, FixedUpdate, tight loops)
- [ ] Collections are pre-sized when capacity is known
- [ ] No unnecessary LINQ in performance-critical code
- [ ] Database/network calls are batched where possible
- [ ] No blocking calls on main thread

## 📚 Documentation

- [ ] Public API has XML doc comments
- [ ] Complex algorithms have inline explanations
- [ ] TODO/HACK comments include context and tracking
- [ ] README updated if public interface changed
