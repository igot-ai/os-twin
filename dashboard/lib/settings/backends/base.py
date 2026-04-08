"""
Canonical VaultBackend protocol and shared types.

Every secret backend -- local keychain, encrypted file, HashiCorp Vault,
GCP Secret Manager, etc. -- must implement the VaultBackend protocol.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, runtime_checkable


class VaultBackendType(str, enum.Enum):
    """Identifies which storage backend is in use."""

    AUTO = "auto"                           # platform-detected (default)
    KEYCHAIN = "keychain"                   # macOS Keychain
    ENCRYPTED_FILE = "encrypted_file"       # AES-encrypted JSON on disk
    ENV = "env"                             # plain environment variables (dev only)
    HASHICORP = "hashicorp"                 # HashiCorp Vault (future)
    GCP_SECRET_MANAGER = "gcp_secret_mgr"  # Google Secret Manager (future)


@dataclass(frozen=True)
class VaultHealthStatus:
    """Result of a backend health check."""

    healthy: bool
    backend_type: str
    message: str = ""
    details: Dict[str, str] = field(default_factory=dict)


@runtime_checkable
class VaultBackend(Protocol):
    """Protocol that every secret backend must satisfy.

    All methods use **scope** / **key** naming consistently.
    Scope is a logical namespace (e.g. ``providers``, ``channels``).
    Key is the secret identifier within that scope.
    """

    # -- CRUD ----------------------------------------------------------------

    def get(self, scope: str, key: str) -> Optional[str]:
        """Return the secret value, or ``None`` if not found."""
        ...

    def set(self, scope: str, key: str, value: str) -> None:
        """Store (or overwrite) a secret."""
        ...

    def delete(self, scope: str, key: str) -> bool:
        """Delete a secret.  Return ``True`` if it existed."""
        ...

    def list_keys(self, scope: str) -> List[str]:
        """Return sorted key names in the given scope."""
        ...

    # -- Introspection -------------------------------------------------------

    @property
    def backend_type(self) -> VaultBackendType:
        """Return the backend type enum value."""
        ...

    def health(self) -> VaultHealthStatus:
        """Return a health check result (non-throwing)."""
        ...
