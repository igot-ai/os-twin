---
name: secure-code-review
description: Deep security-focused code review covering OWASP Top 10 categories, input validation, authentication/authorization logic, cryptographic usage, secrets management, and information leakage. Produces security-specific findings with exploitation context and remediation guidance.
---

# secure-code-review

## Purpose

Security-focused code review catches vulnerabilities that functional reviews miss. While the staff-manager reviews for correctness, this review targets exploitability.

## OWASP Top 10 Checklist

### 1. Injection (A03:2021)
- [ ] All user input is validated and sanitized
- [ ] Parameterized queries / prepared statements used for SQL
- [ ] No string concatenation for query building
- [ ] OS command injection prevented

### 2. Broken Authentication (A07:2021)
- [ ] Passwords hashed with bcrypt/argon2 (not MD5/SHA1)
- [ ] Session tokens are cryptographically random
- [ ] Session invalidation on logout
- [ ] Multi-factor authentication where appropriate
- [ ] Account lockout after failed attempts

### 3. Sensitive Data Exposure (A02:2021)
- [ ] PII is encrypted at rest
- [ ] TLS for all data in transit
- [ ] No sensitive data in logs
- [ ] No sensitive data in error messages
- [ ] No sensitive data in URLs

### 4. Broken Access Control (A01:2021)
- [ ] Authorization checked on every request (not just UI)
- [ ] IDOR (Insecure Direct Object Reference) prevented
- [ ] Role-based access control enforced server-side
- [ ] CORS configured correctly

### 5. Security Misconfiguration (A05:2021)
- [ ] Default credentials changed
- [ ] Unnecessary features disabled
- [ ] Security headers configured (CSP, HSTS, X-Frame-Options)
- [ ] Debug mode disabled in production

### 6. XSS (A03:2021)
- [ ] Output encoding for HTML context
- [ ] Content Security Policy configured
- [ ] No `dangerouslySetInnerHTML` or equivalent without sanitization

### 7. Cryptographic Failures (A02:2021)
- [ ] Using standard, well-tested crypto libraries
- [ ] No custom cryptography implementations
- [ ] Proper key management (not hardcoded)
- [ ] Sufficient key lengths

## Finding Format

```markdown
## Security Finding: [Title]

**Severity:** P0 🔴 | P1 🟠 | P2 🟡 | P3 🔵
**Category:** [OWASP category]
**File:** `[path]` Lines [X–Y]
**CWE:** [CWE ID if applicable]

### Vulnerability
[What the vulnerability is]

### Exploitation Scenario
[How an attacker could exploit this — step by step]

### Impact
[What happens if exploited — data loss, unauthorized access, etc.]

### Remediation
```[language]
// Before (vulnerable)
[vulnerable code]

// After (fixed)
[fixed code]
```

### References
- [OWASP reference]
- [CWE reference]
```

## Anti-Patterns

- Only reviewing for OWASP Top 10 → business logic vulnerabilities exist outside the Top 10
- Flagging everything as critical → boy who cried wolf; accurate severity matters
- Security review as a gate without help → provide fix guidance, not just "this is wrong"
- Ignoring test code → test fixtures with hardcoded credentials can leak
