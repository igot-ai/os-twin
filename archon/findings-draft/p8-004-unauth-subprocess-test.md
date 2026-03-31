Phase: 8
Sequence: 004
Slug: unauth-subprocess-test
Verdict: VALID
Rationale: Unauthenticated subprocess trigger enables DoS and information disclosure, but hardcoded commands prevent command injection, reducing severity to MEDIUM.
Severity-Original: MEDIUM
PoC-Status: pending
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-A/debate.md

## Summary

GET /api/run_pytest_auth and GET /api/test_ws spawn subprocess commands (pytest and test_ws.py) without any authentication. Any network-adjacent client can trigger CPU-intensive test execution and receive full stdout/stderr output, which may contain sensitive configuration values, file paths, and assertion data.

## Location

- `dashboard/routes/system.py:171-185` — `run_pytest_auth` endpoint
- `dashboard/routes/system.py:187-196` — `run_ws_test` endpoint

## Attacker Control

Trigger-only. The attacker can initiate subprocess execution but cannot control the command being run. Commands are hardcoded: `python3 -m pytest test_auth.py -v` and `python3 test_ws.py`.

## Trust Boundary Crossed

Unauthenticated HTTP request → subprocess execution on the server. While the commands are fixed, the trust boundary violation exists: an unauthenticated user should not be able to trigger process creation or read test output.

## Impact

- **DoS**: Repeated requests cause CPU/memory exhaustion via subprocess spawning
- **Information disclosure**: Test output (stdout/stderr) returned to caller may contain file paths, configuration values, assertion failures with sensitive data, and stack traces
- No command injection possible (hardcoded commands)

## Evidence

```python
# dashboard/routes/system.py:171-185
@router.get("/run_pytest_auth")
async def run_pytest_auth():
    import asyncio
    cmd = ["python3", "-m", "pytest", str(PROJECT_ROOT / "test_auth.py"), "-v"]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return {"stdout": stdout.decode(), "stderr": stderr.decode(), "returncode": process.returncode}
```

No `Depends(get_current_user)` in either function signature.

## Reproduction Steps

1. Start the dashboard server
2. Execute: `curl http://localhost:9000/api/run_pytest_auth`
3. Observe test output in response including file paths and test results
4. Execute: `curl http://localhost:9000/api/test_ws`
5. Repeat rapidly to demonstrate DoS potential
