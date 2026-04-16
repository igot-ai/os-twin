"""
Environment-variable vault backend (development / CI only).

Reads secrets from ``os.environ``.  Writes are rejected because env
vars set at runtime do not persist across process restarts.

Use this backend in CI pipelines or development environments where
secrets are injected via environment variables.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from .base import VaultBackendType, VaultHealthStatus

logger = logging.getLogger(__name__)

# Map (scope, key) -> expected env var name.  Extend as needed.
_ENV_MAP: Dict[tuple[str, str], str] = {
    ("providers", "anthropic"): "ANTHROPIC_API_KEY",
    ("providers", "openai"): "OPENAI_API_KEY",
    ("providers", "google"): "GOOGLE_API_KEY",
    ("channels", "telegram"): "TELEGRAM_BOT_TOKEN",
    ("channels", "discord"): "DISCORD_TOKEN",
    ("tunnel", "ngrok"): "NGROK_AUTHTOKEN",
    ("auth", "dashboard"): "OSTWIN_API_KEY",
}


class EnvBackend:
    """Read-only vault backed by environment variables."""

    @property
    def backend_type(self) -> VaultBackendType:
        return VaultBackendType.ENV

    def get(self, scope: str, key: str) -> Optional[str]:
        env_var = _ENV_MAP.get((scope, key))
        if env_var is None:
            return None
        return os.environ.get(env_var) or None

    def set(self, scope: str, key: str, value: str) -> None:
        env_var = _ENV_MAP.get((scope, key))
        if env_var is None:
            raise ValueError(
                f"No env-var mapping for scope={scope!r} key={key!r}. "
                "Use a persistent backend (keychain / encrypted_file) instead."
            )
        # Set in current process only (non-persistent)
        os.environ[env_var] = value
        logger.warning(
            "EnvBackend.set() only sets %s in the current process -- "
            "the value will be lost on restart.",
            env_var,
        )

    def delete(self, scope: str, key: str) -> bool:
        env_var = _ENV_MAP.get((scope, key))
        if env_var and env_var in os.environ:
            del os.environ[env_var]
            return True
        return False

    def list_keys(self, scope: str) -> List[str]:
        keys: List[str] = []
        for (s, k), env_var in _ENV_MAP.items():
            if s == scope and os.environ.get(env_var):
                keys.append(k)
        return sorted(keys)

    def health(self) -> VaultHealthStatus:
        set_count = sum(
            1 for env_var in _ENV_MAP.values() if os.environ.get(env_var)
        )
        return VaultHealthStatus(
            healthy=True,
            backend_type=self.backend_type.value,
            message=f"EnvBackend: {set_count}/{len(_ENV_MAP)} secrets present in env",
            details={"total_mapped": str(len(_ENV_MAP)), "set_count": str(set_count)},
        )
