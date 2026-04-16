"""
macOS Keychain vault backend.

Uses the ``security`` CLI to store secrets in the system keychain.
Only available on macOS (darwin).
"""

from __future__ import annotations

import logging
import subprocess
from typing import List, Optional

from .base import VaultBackendType, VaultHealthStatus

logger = logging.getLogger(__name__)

SERVICE_PREFIX = "ostwin-mcp"
ACCOUNT = "ostwin"


class KeychainBackend:
    """Store secrets in the macOS Keychain via the ``security`` CLI."""

    # -- VaultBackend protocol -----------------------------------------------

    @property
    def backend_type(self) -> VaultBackendType:
        return VaultBackendType.KEYCHAIN

    def get(self, scope: str, key: str) -> Optional[str]:
        service = _service_name(scope, key)
        try:
            result = subprocess.run(
                [
                    "security", "find-generic-password",
                    "-a", ACCOUNT, "-s", service, "-w",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def set(self, scope: str, key: str, value: str) -> None:
        service = _service_name(scope, key)
        # Delete first to handle updates (add-generic-password fails on dupes)
        self.delete(scope, key)
        try:
            subprocess.run(
                [
                    "security", "add-generic-password",
                    "-a", ACCOUNT, "-s", service, "-w", value,
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to set keychain secret: {exc.stderr.decode().strip()}"
            ) from exc

    def delete(self, scope: str, key: str) -> bool:
        service = _service_name(scope, key)
        result = subprocess.run(
            ["security", "delete-generic-password", "-a", ACCOUNT, "-s", service],
            capture_output=True,
        )
        return result.returncode == 0

    def list_keys(self, scope: str) -> List[str]:
        prefix = f"{SERVICE_PREFIX}/{scope}/"
        try:
            result = subprocess.run(
                ["security", "dump-keychain"],
                capture_output=True,
                text=True,
            )
            keys: set[str] = set()
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith('0x00000007 <blob>='):
                    parts = line.split('"')
                    if len(parts) >= 2 and parts[1].startswith(prefix):
                        keys.add(parts[1][len(prefix):])
            return sorted(keys)
        except Exception:
            logger.warning("Failed to list keychain keys for scope=%s", scope)
            return []

    def health(self) -> VaultHealthStatus:
        try:
            result = subprocess.run(
                ["security", "default-keychain"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                keychain = result.stdout.strip().strip('"')
                return VaultHealthStatus(
                    healthy=True,
                    backend_type=self.backend_type.value,
                    message="Keychain accessible",
                    details={"keychain": keychain},
                )
            return VaultHealthStatus(
                healthy=False,
                backend_type=self.backend_type.value,
                message=f"Keychain error: {result.stderr.strip()}",
            )
        except Exception as exc:
            return VaultHealthStatus(
                healthy=False,
                backend_type=self.backend_type.value,
                message=f"Keychain unreachable: {exc}",
            )


# -- helpers -----------------------------------------------------------------

def _service_name(scope: str, key: str) -> str:
    return f"{SERVICE_PREFIX}/{scope}/{key}"
