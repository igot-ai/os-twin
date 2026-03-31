# CodeQL Flow Paths — All Severities

> Generated: 2026-03-30 | CodeQL 2.24.2 | Python DB: 88 files | JS DB: 144 files

## Summary

| Language | Suite | Total Results | Security-Critical |
|----------|-------|---------------|-------------------|
| Python | python-security-and-quality.qls | 268 | 80+ (path-injection, cmd-injection, clear-text) |
| JavaScript | javascript-security-and-quality.qls | 13 | 0 (code quality only) |

## Critical Security Findings

### 1. Command-Line Injection (py/command-line-injection)
- **File**: `dashboard/routes/system.py:168`
- **Severity**: error
- **Flow**: HTTP POST `command` param → `subprocess.run(command, shell=True)`
- **CWE**: CWE-78

### 2. Path Injection — Multiple Locations (py/path-injection)
- **Files**: `dashboard/api_utils.py` (30+ locations), `dashboard/routes/rooms.py`, `dashboard/routes/plans.py`, `dashboard/routes/skills.py`, `dashboard/routes/system.py`
- **Severity**: warning
- **Flow**: URL query/path params → `Path()` construction → filesystem access
- **CWE**: CWE-22

### 3. Clear-Text Storage of Sensitive Data (py/clear-text-storage-sensitive-data)
- **File**: `dashboard/routes/auth.py:50`
- **Severity**: warning
- **Flow**: `_API_KEY` value stored as cookie value in clear text
- **CWE**: CWE-312

### 4. Clear-Text Logging of Sensitive Data (py/clear-text-logging-sensitive-data)
- **File**: `.agents/mcp/config_resolver.py:126`
- **Severity**: warning
- **Flow**: Secret value logged via standard logging
- **CWE**: CWE-312

### 5. Regex Injection (py/regex-injection)
- **File**: `dashboard/routes/plans.py:1019`
- **Severity**: warning
- **Flow**: User query param → `re.match(user_value, ...)`
- **CWE**: CWE-730

### 6. Polynomial ReDoS (py/polynomial-redos)
- **Files**: `dashboard/routes/skills.py:337`, `dashboard/routes/skills.py:349`
- **Severity**: warning
- **CWE**: CWE-1333

### 7. Stack Trace Exposure (py/stack-trace-exposure)
- **Files**: `dashboard/routes/mcp.py:238,300`, `dashboard/routes/plans.py:1184`, `dashboard/routes/roles.py:492`
- **Severity**: warning
- **CWE**: CWE-209

## JavaScript / TypeScript Findings (CodeQL)

All 13 JS results are code quality issues (unused variables, duplicate regex chars) with no security impact.

## DFD-Driven Targeted Analysis Results

| DFD Slice | Custom Rule Triggered | Confirmed? |
|-----------|----------------------|-----------|
| DFD-1: /api/shell RCE | subprocess-shell-true-user-input, fastapi-route-missing-auth-subprocess | YES |
| DFD-2: Prompt Injection | prompt-injection-discord-mention-gemini | YES (manual) |
| DFD-3: Unauthenticated file write | fastapi-route-missing-auth-dependency | YES |
| DFD-4: Vault hardcoded key | hardcoded-fernet-encryption-key | YES |
| DFD-5: DEBUG bypass | debug-auth-bypass-key | YES |
| DFD-6: Cookie missing secure | cookie-missing-secure-flag | YES |
