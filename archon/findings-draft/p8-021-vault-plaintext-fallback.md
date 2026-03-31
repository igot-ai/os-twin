Phase: 8
Sequence: 021
Slug: vault-plaintext-fallback
Verdict: VALID
Rationale: Vault stores credentials as plaintext JSON when cryptography package is absent, which is the default state per requirements.txt; combined with world-readable file permissions, any local process can read all stored secrets without any cryptographic barrier.
Severity-Original: HIGH
PoC-Status: pending
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-B/debate.md

## Summary

When the `cryptography` Python package is not installed, `EncryptedFileVault` silently falls back to storing all vault data as plaintext JSON (vault.py:143-145). The `cryptography` package is NOT listed in `.agents/mcp/requirements.txt`, making this plaintext mode the default behavior in minimal installations that follow the project's own dependency specification. The vault file at `~/.ostwin/mcp/.vault.enc` (misleadingly named `.enc`) contains raw JSON readable by any process with file access.

## Location

- **Import guard**: `.agents/mcp/vault.py:10-16` -- `CRYPTOGRAPHY_AVAILABLE = False` on ImportError
- **Fernet disabled**: `.agents/mcp/vault.py:104` -- `self.fernet = ... if CRYPTOGRAPHY_AVAILABLE else None`
- **Plaintext write**: `.agents/mcp/vault.py:143-145` -- `f.write(json_data)` (raw JSON bytes)
- **Plaintext read**: `.agents/mcp/vault.py:131-132` -- `json.loads(encrypted_data)` (direct parse)
- **Missing dependency**: `.agents/mcp/requirements.txt` -- `cryptography` not listed

## Attacker Control

No attacker input needed. The fallback activates automatically when the `cryptography` package is not installed. The attacker only needs file read access.

## Trust Boundary Crossed

Local process isolation boundary. Any process on the system (malware, compromised service, co-tenant) can read plaintext secrets.

## Impact

- All MCP vault secrets stored in cleartext with no cryptographic protection
- File extension `.vault.enc` is misleading -- suggests encryption when none exists
- No runtime warning emitted to alert the user
- Affects all installations following `.agents/mcp/requirements.txt` without manually adding `cryptography`

## Evidence

1. `vault.py:10-16` -- conditional import with silent fallback
2. `vault.py:104` -- `self.fernet = Fernet(self.key) if CRYPTOGRAPHY_AVAILABLE else None`
3. `vault.py:143-145` -- plaintext write path: `f.write(json_data)`
4. `vault.py:131-132` -- plaintext read path: `json.loads(encrypted_data)`
5. `.agents/mcp/requirements.txt` -- `cryptography` absent from dependency list

## Reproduction Steps

1. Create a fresh Python virtualenv and install only `.agents/mcp/requirements.txt`
2. Verify: `python -c "import cryptography"` raises ImportError
3. Run: `python vault.py set test-server api-key secret123`
4. Read the vault file: `cat ~/.ostwin/mcp/.vault.enc`
5. Confirm the output is plaintext JSON containing `{"test-server": {"api-key": "secret123"}}`

## Cold Verification

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Code path at vault.py:143-145 unambiguously writes plaintext JSON when cryptography is absent (the default per requirements.txt), with no file permission restrictions, affecting non-macOS platforms.
Severity-Final: MEDIUM
PoC-Status: theoretical
```

### Verification Notes

**Verdict: CONFIRMED but DOWNGRADED from HIGH to MEDIUM.**

The vulnerability is real. The code path is unambiguous: when `CRYPTOGRAPHY_AVAILABLE` is `False` (lines 10-16), `self.fernet` is set to `None` (line 104), and `_save_data` writes raw JSON bytes with no encryption (lines 143-145). The `cryptography` package is not listed in `requirements.txt` and is not a transitive dependency of any listed package. No `chmod` or restrictive permissions are applied to the vault file (default 0644, world-readable).

**Severity downgraded from HIGH to MEDIUM for the following reasons:**

1. **macOS is not affected**: `get_vault()` (line 169) returns `MacOSKeychainVault` on `sys.platform == "darwin"`, completely bypassing `EncryptedFileVault`. The finding draft fails to mention this significant scope limitation.
2. **Local access required**: Exploitation requires local file read access to the user's home directory -- not remotely triggerable.
3. **Marginal security difference**: The companion finding (p8-020) documents that even WITH `cryptography` installed, the default encryption key is a hardcoded known value (`ostwin-default-insecure-key-32ch`). The practical security gain of encryption with a published key is minimal.
4. **Theoretical PoC only**: Full end-to-end reproduction on an affected (Linux) platform was not performed; code analysis confirms the path but no runtime proof on target OS.

**Full review**: `security/adversarial-reviews/vault-plaintext-fallback-review.md`
