Phase: 8
Sequence: 020
Slug: vault-hardcoded-key
Verdict: VALID
Rationale: Hardcoded cryptographic key in production vault code with world-readable file permissions allows any local user to decrypt all stored MCP service credentials on non-macOS systems; macOS Keychain provides protection only for that platform.
Severity-Original: HIGH
PoC-Status: pending
Pre-FP-Flag: none
Debate: security/chamber-workspace/chamber-B/debate.md

## Summary

The `EncryptedFileVault` class in `.agents/mcp/vault.py` uses a hardcoded fallback encryption key `ostwin-default-insecure-key-32ch` (line 117) when the `OSTWIN_VAULT_KEY` environment variable is not set. On non-macOS systems, this is the default vault backend. The encrypted vault file at `~/.ostwin/mcp/.vault.enc` is created with the process default umask (typically 0644, world-readable). Any local OS user can read the file and decrypt it using the publicly known key, exposing all stored MCP API keys and service credentials (GitHub tokens, Slack tokens, etc.).

## Location

- **Primary**: `.agents/mcp/vault.py:117` -- hardcoded key `b"ostwin-default-insecure-key-32ch"`
- **Key derivation**: `.agents/mcp/vault.py:106-117` -- `_get_encryption_key()` method
- **File write (no chmod)**: `.agents/mcp/vault.py:136-142` -- `_save_data()` method
- **Platform gate**: `.agents/mcp/vault.py:168-173` -- `get_vault()` returns `EncryptedFileVault` on non-macOS

## Attacker Control

The attacker does not need to control any input. The hardcoded key is embedded in the public source code. The attacker only needs local file read access to `~/.ostwin/mcp/.vault.enc`, which is world-readable under default umask.

Decryption one-liner:
```python
from cryptography.fernet import Fernet
import base64, json
key = base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch")
data = open(os.path.expanduser("~/.ostwin/mcp/.vault.enc"), "rb").read()
print(json.loads(Fernet(key).decrypt(data)))
```

## Trust Boundary Crossed

Local user-to-user boundary on shared systems. A non-privileged OS user can access another user's MCP vault secrets.

## Impact

- All stored MCP service credentials (API keys, tokens) exposed
- Enables lateral movement to connected services (GitHub, Slack, etc.)
- No key rotation mechanism exists -- compromise is persistent until credentials are manually rotated on each service
- Affects all non-macOS deployments using default configuration

## Evidence

1. `vault.py:117` -- `return base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch")` -- hardcoded fallback
2. `vault.py:107-113` -- env var check only used when `OSTWIN_VAULT_KEY` is set
3. `vault.py:141-142` -- `open(self.path, "wb")` with no subsequent `os.chmod()`
4. `vault.py:168-173` -- `get_vault()` uses `EncryptedFileVault` on all non-macOS platforms
5. `.agents/mcp/requirements.txt` -- does not enforce `OSTWIN_VAULT_KEY` setup

## Reproduction Steps

1. On a Linux system, ensure `OSTWIN_VAULT_KEY` is NOT set in the environment
2. Run the MCP vault to store a test secret: `python vault.py set test-server api-key secret123`
3. Verify file permissions: `ls -la ~/.ostwin/mcp/.vault.enc` -- expect 0644 (world-readable)
4. As a different OS user, run the decryption one-liner above
5. Confirm the test secret is recovered in cleartext

## Cold Verification

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Hardcoded key at vault.py:117 is verified in source; no application-level file permission restriction exists; OS home directory permissions are the only defense and are not universally restrictive.
Severity-Final: MEDIUM
PoC-Status: blocked
```

### Verification Notes

**Code path independently confirmed**: The hardcoded key `b"ostwin-default-insecure-key-32ch"` at line 117 is the default encryption key on all non-macOS platforms when `OSTWIN_VAULT_KEY` is not set. The `_save_data()` method writes the vault file with no `os.chmod()` call, and no `os.umask()` is set anywhere in the module.

**Severity downgraded from HIGH to MEDIUM**: The finding requires local access to a shared multi-user system where home directories are not restricted to 0700. Many modern Linux distributions (Ubuntu 21.04+, Fedora) default home directories to 0700, which provides OS-level protection the application does not control. The combination of (1) local-only access, (2) non-macOS requirement, (3) shared system requirement, and (4) permissive home directory permissions constitutes significant preconditions that prevent a HIGH rating.

**PoC blocked**: Verification host is macOS (darwin), where `get_vault()` returns `MacOSKeychainVault`. The vulnerable `EncryptedFileVault` path is only reachable on non-macOS platforms. Code analysis confirms the vulnerability is real in applicable environments.

**Full review**: `security/adversarial-reviews/vault-hardcoded-key-review.md`
