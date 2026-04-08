"""
Vault backend implementations.

This package contains the canonical VaultBackend protocol and all
concrete backend implementations.  When adding a new backend (e.g.
HashiCorp Vault, GCP Secret Manager), add a module here and register
it in the BACKEND_REGISTRY.
"""

from .base import VaultBackend, VaultBackendType, VaultHealthStatus
from .factory import create_backend, BACKEND_REGISTRY

__all__ = [
    "VaultBackend",
    "VaultBackendType",
    "VaultHealthStatus",
    "create_backend",
    "BACKEND_REGISTRY",
]
