# Adversarial Review: vault-hardcoded-key

## Step 1 -- Restate and Decompose

**Vulnerability claim in my own words**: The encrypted file vault used on non-macOS systems defaults to a cryptographic key that is hardcoded in the source code. Because the vault file is written without restrictive file permissions, any local user on a shared system who can read the file can trivially decrypt all stored MCP service credentials using the publicly visible key.

### Sub-claims

- **Sub-claim A (Hardcoded key exists)**: The encryption key `b"ostwin-default-insecure-key-32ch"` is embedded in source at vault.py:117 and used when the `OSTWIN_VAULT_KEY` environment variable is absent.
  - **Status**: CONFIRMED. Verified directly at line 117.

- **Sub-claim B (File permissions are not restricted)**: The vault file is written via `open(self.path, "wb")` with no subsequent `os.chmod()` or prior `os.umask()` call, leaving permissions at the process default umask.
  - **Status**: CONFIRMED. No chmod/umask calls exist anywhere in vault.py.

- **Sub-claim C (Decryption possible by any local reader)**: Any user who can read the vault file can decrypt it using the known key and standard Fernet decryption.
  - **Status**: LOGICALLY FOLLOWS from A + B. The Fernet key is deterministic and publicly known.

No sub-claim failures.

## Step 2 -- Independent Code Path Trace

Traced from `get_vault()` (line 168):

1. `get_vault()` checks `sys.platform == "darwin"`. If false, creates `EncryptedFileVault(Path.home() / ".ostwin" / "mcp" / ".vault.enc")`.
2. `EncryptedFileVault.__init__()` (line 101-104) calls `_get_encryption_key()`.
3. `_get_encryption_key()` (line 106-117):
   - Checks `os.environ.get("OSTWIN_VAULT_KEY")`.
   - If not set (default), returns `base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch")`.
4. `_save_data()` (line 136-145):
   - `self.path.parent.mkdir(parents=True, exist_ok=True)` -- no restrictive mode argument.
   - `open(self.path, "wb")` -- no `os.chmod()` after write.
5. The Fernet instance is created from the hardcoded key, encryption and decryption are standard Fernet operations.

**Validations/sanitizations on path**: None relevant to security. The only check is whether `OSTWIN_VAULT_KEY` env var is set.

**Discrepancies with draft**: None. The draft accurately describes the code path.

## Step 3 -- Protection Surface Search

| Layer | Protection | Blocks Attack? |
|-------|-----------|---------------|
| Language | Python -- no relevant type system protection | No |
| Framework | No framework protections apply (standalone script) | No |
| Middleware | N/A (local file operation) | No |
| Application | `OSTWIN_VAULT_KEY` env var override | Only if explicitly set by user (not default) |
| Application | macOS Keychain backend | Only on macOS (non-macOS unprotected) |
| OS | Home directory permissions (often 0700 on Linux) | PARTIAL -- system-dependent, not enforced by app |
| Documentation | Code comment at line 115 says "insecure" | Acknowledges risk, does not mitigate |

**Key finding**: The home directory permission (often 0700 on many modern Linux distributions like Ubuntu, Fedora) is a significant OS-level protection that the finding does not adequately address. On systems where home directories are 0700, other users cannot traverse into `~/.ostwin/` regardless of the vault file's own permissions. However, this is not universal (some distros use 0755, shared hosting environments may vary), and the application does not enforce it.

## Step 4 -- Real-Environment Reproduction

**Environment**: macOS (darwin) -- the current host.

**Blocker**: On macOS, `get_vault()` returns `MacOSKeychainVault`, not `EncryptedFileVault`. The vulnerable code path is only reachable on non-macOS platforms.

**Attempted workaround**: Could monkey-patch `sys.platform` but that would not test real-world conditions.

**PoC-Status**: blocked (platform mismatch -- macOS host cannot exercise non-macOS code path without patching)

The vulnerability is assessed based on code analysis alone.

## Step 5 -- Prosecution and Defense Briefs

### Prosecution Brief

The hardcoded key at vault.py:117 is an unambiguous cryptographic weakness. The key `b"ostwin-default-insecure-key-32ch"` is visible in the public source code. On non-macOS systems (Linux, Windows), this is the DEFAULT encryption key -- no user action is required to be vulnerable.

The `_save_data()` method (line 136-145) writes the encrypted file without any `os.chmod()` call. The `mkdir()` on line 137 also uses no restrictive mode parameter. Under common umask values (0022), the vault file would be created as 0644 (world-readable) and the directory as 0755 (world-traversable).

The attack requires only: (1) read access to the victim's vault file, and (2) knowledge of the hardcoded key from the source code. The decryption is a single Fernet operation with no rate limiting, no key derivation function overhead, and no additional authentication.

The code comment at line 115 explicitly acknowledges the key is "insecure", confirming this is a known but unmitigated design flaw.

### Defense Brief

The primary trust boundary crossing (user-to-user file access) depends on the OS home directory permissions. On many modern Linux distributions (Ubuntu 21.04+, Fedora, etc.), home directories default to 0700, which would prevent other local users from accessing `~/.ostwin/mcp/.vault.enc` regardless of the file's own permissions.

The vulnerability requires LOCAL access to a SHARED system. This significantly limits the attack surface compared to a remote vulnerability. Single-user systems (personal laptops, VMs, containers) are not affected because there is no second user to exploit the weakness.

Users CAN mitigate by setting the `OSTWIN_VAULT_KEY` environment variable (vault.py:107-113). While this is not enforced, it is available.

The `EncryptedFileVault` is described as a fallback ("better than plaintext" per the code comment). It is not positioned as a production-grade secret store.

## Step 6 -- Severity Challenge

Starting at MEDIUM.

**Upgrade considerations**:
- Remotely triggerable? NO -- requires local access to the filesystem.
- Trust boundary crossing? YES -- user-to-user on shared systems.
- Significant preconditions? YES -- requires (1) non-macOS system, (2) shared multi-user system, (3) `OSTWIN_VAULT_KEY` not set, (4) home directory permissions allow traversal.

**Downgrade signals**:
- Requires local access (not remote).
- Requires multi-user shared system.
- Requires non-default on some modern Linux distros (home dir 0700).
- OS-level protection (home directory permissions) may block on many systems.
- PoC could not be executed (platform blocked).

**Challenged severity**: MEDIUM. The finding draft rated HIGH, but the local-access-only nature, the dependence on home directory permissions being permissive, and the multi-user system requirement are significant preconditions that prevent an upgrade from MEDIUM. The lower severity (MEDIUM) wins per protocol.

## Step 7 -- Verdict

The code analysis confirms the hardcoded key exists, is the default on non-macOS, and the file permissions are not restricted by the application. However, reproduction was blocked by platform constraints, and the OS-level home directory permission (often 0700 on modern Linux) provides a significant but not universal defense.

The prosecution case is strong on code analysis. The defense case identifies real mitigating factors but none that universally block the attack. The vulnerability is genuine in environments where home directories are world-readable.

```
Adversarial-Verdict: CONFIRMED
Adversarial-Rationale: Hardcoded key at vault.py:117 is verified in source; no application-level file permission restriction exists; OS home directory permissions are the only defense and are not universally restrictive.
Severity-Final: MEDIUM
PoC-Status: blocked
```
