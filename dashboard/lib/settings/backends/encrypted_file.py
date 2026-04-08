"""
Encrypted-file vault backend.

Stores secrets in a single AES-encrypted JSON file on disk.
Used as the fallback on non-macOS platforms.

Security notes
--------------
* Uses Fernet (AES-128-CBC + HMAC-SHA256) when ``cryptography`` is installed.
* The encryption key is derived from ``OSTWIN_VAULT_KEY`` env var via
  PBKDF2-HMAC-SHA256 with a fixed salt and 480 000 iterations.
* If ``cryptography`` is missing, secrets are stored as plaintext JSON
  and a warning is emitted on every operation.
* File permissions are enforced to 0o600 on write.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import stat
from pathlib import Path
from typing import Dict, List, Optional

from .base import VaultBackend, VaultBackendType, VaultHealthStatus

logger = logging.getLogger(__name__)

# Try to import cryptography -- graceful degradation when missing
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False

# KDF parameters (fixed salt is acceptable because the passphrase is
# machine-specific and the file is already permission-locked).
_KDF_SALT = b"ostwin-vault-kdf-salt-v1"
_KDF_ITERATIONS = 480_000
_DEFAULT_PASSPHRASE = b"ostwin-local-default-passphrase"


class EncryptedFileBackend:
    """AES-encrypted JSON file on disk."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or (Path.home() / ".ostwin" / "vault" / ".vault.enc")
        self._fernet = _build_fernet()

    # -- VaultBackend protocol -----------------------------------------------

    @property
    def backend_type(self) -> VaultBackendType:
        return VaultBackendType.ENCRYPTED_FILE

    def get(self, scope: str, key: str) -> Optional[str]:
        data = self._load()
        return data.get(scope, {}).get(key)

    def set(self, scope: str, key: str, value: str) -> None:
        data = self._load()
        data.setdefault(scope, {})[key] = value
        self._save(data)

    def delete(self, scope: str, key: str) -> bool:
        data = self._load()
        if scope in data and key in data[scope]:
            del data[scope][key]
            if not data[scope]:
                del data[scope]
            self._save(data)
            return True
        return False

    def list_keys(self, scope: str) -> List[str]:
        data = self._load()
        return sorted(data.get(scope, {}).keys())

    def health(self) -> VaultHealthStatus:
        details: Dict[str, str] = {
            "path": str(self.path),
            "encrypted": str(_CRYPTO_AVAILABLE),
        }
        if not _CRYPTO_AVAILABLE:
            return VaultHealthStatus(
                healthy=True,
                backend_type=self.backend_type.value,
                message="WARNING: cryptography not installed -- secrets stored as plaintext",
                details=details,
            )
        try:
            self._load()
            return VaultHealthStatus(
                healthy=True,
                backend_type=self.backend_type.value,
                message="Encrypted vault accessible",
                details=details,
            )
        except Exception as exc:
            return VaultHealthStatus(
                healthy=False,
                backend_type=self.backend_type.value,
                message=f"Vault read error: {exc}",
                details=details,
            )

    # -- internal ------------------------------------------------------------

    def _load(self) -> Dict[str, Dict[str, str]]:
        if not self.path.exists():
            return {}
        raw = self.path.read_bytes()
        if not raw:
            return {}
        try:
            if self._fernet:
                decrypted = self._fernet.decrypt(raw)
                return json.loads(decrypted)
            else:
                logger.warning("cryptography not installed -- reading plaintext vault")
                return json.loads(raw)
        except Exception:
            logger.warning("Failed to read vault file at %s", self.path)
            return {}

    def _save(self, data: Dict[str, Dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, sort_keys=True).encode()
        if self._fernet:
            payload = self._fernet.encrypt(payload)
        else:
            logger.warning("cryptography not installed -- writing plaintext vault")
        self.path.write_bytes(payload)
        # Enforce restrictive file permissions
        try:
            self.path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except OSError:
            pass  # Windows or permission issue


# -- module-level helpers ---------------------------------------------------

def _build_fernet():
    """Derive a Fernet instance from OSTWIN_VAULT_KEY or the default passphrase."""
    if not _CRYPTO_AVAILABLE:
        return None
    passphrase = os.environ.get("OSTWIN_VAULT_KEY", "").encode() or _DEFAULT_PASSPHRASE
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KDF_SALT,
        iterations=_KDF_ITERATIONS,
    )
    derived = kdf.derive(passphrase)
    return Fernet(base64.urlsafe_b64encode(derived))
