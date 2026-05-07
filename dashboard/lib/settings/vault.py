"""
Settings Vault -- the single entry-point for secret management.

Wraps a pluggable ``VaultBackend`` (keychain, encrypted-file, env,
HashiCorp, GCP Secret Manager, ...) and adds:

* Scope validation so callers can't invent arbitrary namespaces.
* A ``list_keys`` helper that returns ``{key: {"is_set": True}}``.
* Thread-safe singleton via ``get_vault()``.
* Health-check delegation.

To switch backends set ``OSTWIN_VAULT_BACKEND`` env var to one of:
  keychain | encrypted_file | env | hashicorp | gcp_secret_mgr
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from .backends import VaultBackend, VaultBackendType, VaultHealthStatus, create_backend

logger = logging.getLogger(__name__)

# Scopes that the settings layer recognises.
# If a cloud backend uses a different namespace model, override this
# at the backend level -- SettingsVault enforces the logical API.
VALID_SCOPES = frozenset({"providers", "channels", "tunnel", "auth", "memory", "knowledge"})


class SettingsVault:
    """Application-level vault with scope validation.

    Delegates all storage to the underlying ``VaultBackend``.
    """

    def __init__(
        self,
        backend: Optional[VaultBackend] = None,
        *,
        backend_type: Optional[VaultBackendType] = None,
    ) -> None:
        self._backend: VaultBackend = backend or create_backend(backend_type)

    # -- scope guard ---------------------------------------------------------

    @staticmethod
    def _validate_scope(scope: str) -> None:
        if scope not in VALID_SCOPES:
            raise ValueError(
                f"Invalid scope: {scope!r}. Must be one of {sorted(VALID_SCOPES)}"
            )

    # -- CRUD ----------------------------------------------------------------

    def get(self, scope: str, key: str) -> Optional[str]:
        """Return the secret value, or ``None`` if not found."""
        self._validate_scope(scope)
        return self._backend.get(scope, key)

    def set(self, scope: str, key: str, value: str) -> None:
        """Store (or overwrite) a secret."""
        self._validate_scope(scope)
        self._backend.set(scope, key, value)

    def delete(self, scope: str, key: str) -> bool:
        """Delete a secret.  Return ``True`` if it existed."""
        self._validate_scope(scope)
        try:
            return self._backend.delete(scope, key)
        except Exception:
            logger.warning("Failed to delete vault key %s/%s", scope, key)
            return False

    def list_keys(self, scope: str) -> Dict[str, Any]:
        """List all keys in *scope* with their status.

        Returns ``{key: {"is_set": True}}`` for every key present.
        """
        self._validate_scope(scope)
        keys: List[str] = self._backend.list_keys(scope)
        return {k: {"is_set": True} for k in keys}

    # -- introspection -------------------------------------------------------

    @property
    def backend_type(self) -> VaultBackendType:
        """Return the active backend type."""
        return self._backend.backend_type

    def health(self) -> VaultHealthStatus:
        """Delegate health check to the backend."""
        return self._backend.health()


# ---------------------------------------------------------------------------
# Thread-safe singleton
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_vault_instance: Optional[SettingsVault] = None


def get_vault(
    *,
    backend: Optional[VaultBackend] = None,
    backend_type: Optional[VaultBackendType] = None,
) -> SettingsVault:
    """Return (or create) the singleton ``SettingsVault``.

    On first call the backend is resolved via the factory.  Subsequent
    calls return the same instance.  Pass *backend* explicitly in tests.
    """
    global _vault_instance
    if _vault_instance is not None:
        return _vault_instance
    with _lock:
        # Double-check after acquiring lock
        if _vault_instance is None:
            _vault_instance = SettingsVault(backend=backend, backend_type=backend_type)
    return _vault_instance


def reset_vault() -> None:
    """Reset the singleton (for testing)."""
    global _vault_instance
    with _lock:
        _vault_instance = None
