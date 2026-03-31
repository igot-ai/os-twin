# Adversarial Review: vault-plaintext-fallback

## Step 1 -- Restate and Decompose

**Vulnerability claim in my own words**: The `EncryptedFileVault` class silently degrades to writing secrets as unencrypted JSON when the `cryptography` Python package is not installed. Since `cryptography` is not a declared dependency in `requirements.txt`, a standard installation on non-macOS systems results in all vault secrets being stored in cleartext in a file with world-readable permissions and a misleading `.enc` extension.

### Sub-claims

- **Sub-claim A**: The `cryptography` package is not guaranteed to be installed. It is absent from `requirements.txt` and is not a transitive dependency of any listed package.
- **Sub-claim B**: When `CRYPTOGRAPHY_AVAILABLE` is `False`, `EncryptedFileVault._save_data()` writes raw JSON bytes to the vault file with no encryption.
- **Sub-claim C**: The vault file is created with default umask permissions (typically 0644), making it readable by any local process. No `chmod` or restrictive permissions are applied.

All sub-claims are coherent and testable.

**Important scoping note**: On macOS (`sys.platform == "darwin"`), `get_vault()` returns `MacOSKeychainVault`, which uses the macOS Keychain and is NOT affected by this vulnerability. This finding only applies to non-macOS platforms (Linux, etc.).

## Step 2 -- Independent Code Path Trace

Starting from `vault.py`:

1. **Lines 10-16**: `try/except ImportError` sets `CRYPTOGRAPHY_AVAILABLE = False` when cryptography is missing. Silent fallback, no warning.
2. **Line 104**: `self.fernet = Fernet(self.key) if CRYPTOGRAPHY_AVAILABLE else None` -- fernet is `None`.
3. **Lines 136-145** (`_save_data`):
   - Line 138: `json_data = json.dumps(data).encode()` -- raw JSON bytes
   - Line 139: `if self.fernet:` -- evaluates to `False`
   - Lines 143-145: `with open(self.path, "wb") as f: f.write(json_data)` -- writes plaintext
4. **Lines 119-134** (`_load_data`):
   - Line 127: `if self.fernet:` -- evaluates to `False`
   - Lines 131-132: `return json.loads(encrypted_data)` -- reads plaintext directly
5. **Lines 168-173** (`get_vault`):
   - Line 169: `if sys.platform == "darwin": return MacOSKeychainVault()` -- macOS bypasses this entirely
   - Lines 172-173: Non-macOS returns `EncryptedFileVault(~/.ostwin/mcp/.vault.enc)`

**Validations/sanitizations on path**: NONE. No `chmod`, no `os.umask`, no `stat` check, no warning, no exception.

**Discrepancy from draft**: The draft does not mention that macOS is not affected (it uses `MacOSKeychainVault`). This narrows the attack surface to Linux/other platforms only.

## Step 3 -- Protection Surface Search

| Layer | Protection | Blocks Attack? |
|-------|-----------|---------------|
| Language | Python type system | No |
| Framework | None applicable | No |
| Middleware | None | No |
| Application -- File permissions | No `chmod` call; default umask 0644 | No -- world-readable |
| Application -- Platform guard | macOS uses Keychain instead | Partially -- macOS only |
| Application -- Warning/error | No warning when fallback activates | No |
| Dependency | `cryptography` could be a transitive dep | Checked: NOT a transitive dep of any requirement |
| Documentation | Code comment says "NOT RECOMMENDED" at line 131 | Informational only |

**Key finding**: On non-macOS systems, there is zero protection against plaintext storage when cryptography is absent.

## Step 4 -- Real-Environment Reproduction

**Environment**: macOS Darwin 25.3.0, Python 3.14, cryptography 46.0.5 installed

**Healthcheck**: Python and vault.py import successfully.

**Attempt 1**: Direct execution of `EncryptedFileVault` with cryptography installed. Result: Fernet encryption active, file is encrypted. This confirms the ENCRYPTED path works.

**Attempt 2**: Simulated `CRYPTOGRAPHY_AVAILABLE = False` by replicating the exact code path from `_save_data` with `fernet = None`. Result: File written as plaintext JSON `{"test-server": {"api-key": "secret123"}}` with permissions `0o100644` (world-readable).

**Attempt 3**: Verified `cryptography` is NOT a dependency of any package in requirements.txt. `pip show` confirms it is only required-by: `azure-identity, azure-storage-blob, msal` -- none of which are in the project's requirements.

**Blocker note**: Cannot fully reproduce on macOS because `get_vault()` returns `MacOSKeychainVault` on darwin. The `EncryptedFileVault` code path is reachable only on non-macOS. The code analysis is definitive however -- the plaintext fallback path is trivially verified by reading the source.

**PoC-Status**: theoretical (full end-to-end on Linux not tested, but code path verified by manual simulation)

## Step 5 -- Prosecution and Defense Briefs

### Prosecution Brief

The vulnerability is genuine on non-macOS platforms:

1. `cryptography` is NOT in `requirements.txt` (verified). It is not a transitive dependency of `mcp[cli]`, `fastapi`, `uvicorn`, `aiofiles`, or `deepagents`.
2. `vault.py:104` sets `self.fernet = None` when `CRYPTOGRAPHY_AVAILABLE` is `False`.
3. `vault.py:143-145` writes raw JSON bytes to `~/.ostwin/mcp/.vault.enc` with no encryption.
4. No `chmod` or `umask` is applied; default file permissions are 0644 (world-readable).
5. The file extension `.vault.enc` is actively misleading, suggesting encryption when none exists.
6. No runtime warning is emitted to alert the user.
7. Any local process (malware, co-tenant, compromised service) can read all stored MCP credentials.

### Defense Brief

1. **macOS is unaffected**: On macOS (likely a significant portion of developer users), `get_vault()` returns `MacOSKeychainVault` which uses the system keychain. The `EncryptedFileVault` path is never reached on macOS.
2. **Local access required**: Exploitation requires read access to the user's home directory, which already implies a significant level of compromise.
3. **Transitive dependency possibility**: While `cryptography` is not a direct or verified transitive dependency, it is extremely common in Python environments and may be present coincidentally.
4. **Even with cryptography, the key is hardcoded**: Finding p8-020 documents that the default encryption key is a hardcoded known value (`ostwin-default-insecure-key-32ch`). So even with cryptography installed, the encryption provides minimal real security.
5. **The code comments acknowledge the issue**: Line 131 says "NOT RECOMMENDED", indicating awareness.

## Step 6 -- Severity Challenge

Starting at MEDIUM.

**Upgrade signals**:
- Secrets exposure (credentials for MCP servers)
- Silent degradation with no user warning
- Default state per requirements.txt on Linux

**Downgrade signals**:
- Requires local file access (not remotely triggerable)
- macOS (likely primary developer platform) is not affected
- Even with cryptography, the hardcoded key (p8-020) provides equivalent weakness
- Theoretical PoC only (not executed on actual Linux target)

**Challenged severity**: MEDIUM. The local-access requirement and macOS exclusion are significant downgrade signals. The fact that the "encrypted" path also uses a hardcoded known key (per p8-020) means the practical security difference between plaintext and "encrypted" is minimal.

Since MEDIUM < HIGH (Severity-Original), the lower severity wins: **MEDIUM**.

## Step 7 -- Verdict

**Adversarial-Verdict**: CONFIRMED
**Adversarial-Rationale**: Code path at vault.py:143-145 unambiguously writes plaintext JSON when cryptography is absent (the default per requirements.txt), with no file permission restrictions, affecting non-macOS platforms.
**Severity-Final**: MEDIUM
**PoC-Status**: theoretical

The finding is real but overstated in severity. It affects only non-macOS platforms, requires local file access, and the "encrypted" alternative (hardcoded key) provides minimal additional security. Downgraded from HIGH to MEDIUM.
