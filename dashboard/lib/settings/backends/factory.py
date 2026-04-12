"""
Vault backend factory.

Resolves which concrete backend to use based on:
1. Explicit ``OSTWIN_VAULT_BACKEND`` env var  (highest priority)
2. ``vault.backend`` key in config.json       (second priority)
3. Platform auto-detection                    (fallback)

To add a new backend:
  1. Create a module in this package (e.g. ``hashicorp.py``).
  2. Register it in ``BACKEND_REGISTRY`` below.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Callable, Dict, Optional

from .base import VaultBackend, VaultBackendType

logger = logging.getLogger(__name__)


# -- Backend constructors ---------------------------------------------------
# Each entry maps a VaultBackendType to a zero-arg callable that returns
# a VaultBackend instance.

def _make_keychain():
    from .keychain import KeychainBackend
    return KeychainBackend()


def _make_encrypted_file():
    from .encrypted_file import EncryptedFileBackend
    return EncryptedFileBackend()


def _make_env():
    from .env import EnvBackend
    return EnvBackend()


BACKEND_REGISTRY: Dict[VaultBackendType, Callable[[], VaultBackend]] = {
    VaultBackendType.KEYCHAIN: _make_keychain,
    VaultBackendType.ENCRYPTED_FILE: _make_encrypted_file,
    VaultBackendType.ENV: _make_env,
    # Future:
    # VaultBackendType.HASHICORP: _make_hashicorp,
    # VaultBackendType.GCP_SECRET_MANAGER: _make_gcp,
}


def create_backend(
    backend_type: Optional[VaultBackendType] = None,
) -> VaultBackend:
    """Create a vault backend instance.

    Resolution order:
    1. ``backend_type`` argument (if not None / AUTO)
    2. ``OSTWIN_VAULT_BACKEND`` env var
    3. Platform auto-detection (macOS -> keychain, else -> encrypted_file)
    """
    resolved = backend_type

    # 1. Env-var override
    if resolved is None or resolved == VaultBackendType.AUTO:
        env_val = os.environ.get("OSTWIN_VAULT_BACKEND", "").strip().lower()
        if env_val:
            try:
                resolved = VaultBackendType(env_val)
            except ValueError:
                logger.warning(
                    "Unknown OSTWIN_VAULT_BACKEND=%r, falling back to auto",
                    env_val,
                )
                resolved = None

    # 2. Platform auto-detection
    if resolved is None or resolved == VaultBackendType.AUTO:
        if sys.platform == "darwin":
            resolved = VaultBackendType.KEYCHAIN
        else:
            resolved = VaultBackendType.ENCRYPTED_FILE

    # 3. Look up constructor
    ctor = BACKEND_REGISTRY.get(resolved)
    if ctor is None:
        raise ValueError(
            f"No registered backend for {resolved!r}.  "
            f"Available: {sorted(r.value for r in BACKEND_REGISTRY)}"
        )

    logger.info("Vault backend: %s", resolved.value)
    return ctor()
