import os
import sys
import subprocess
import json
import base64
from abc import ABC, abstractmethod
from pathlib import Path

# Try to import cryptography, fallback if not available
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

class VaultStore(ABC):
    @abstractmethod
    def set(self, server: str, key: str, value: str):
        pass

    @abstractmethod
    def get(self, server: str, key: str) -> str:
        pass

    @abstractmethod
    def delete(self, server: str, key: str):
        pass

    @abstractmethod
    def list_keys(self, server: str) -> list[str]:
        pass

class MacOSKeychainVault(VaultStore):
    SERVICE_PREFIX = "ostwin-mcp"
    ACCOUNT = "ostwin"

    def _get_service_name(self, server: str, key: str) -> str:
        return f"{self.SERVICE_PREFIX}/{server}/{key}"

    def set(self, server: str, key: str, value: str):
        service = self._get_service_name(server, key)
        # Try to delete first in case it already exists
        self.delete(server, key)
        try:
            subprocess.run(
                ["security", "add-generic-password", "-a", self.ACCOUNT, "-s", service, "-w", value],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to set keychain password: {e.stderr.decode().strip()}")

    def get(self, server: str, key: str) -> str:
        service = self._get_service_name(server, key)
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-a", self.ACCOUNT, "-s", service, "-w"],
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def delete(self, server: str, key: str):
        service = self._get_service_name(server, key)
        subprocess.run(
            ["security", "delete-generic-password", "-a", self.ACCOUNT, "-s", service],
            capture_output=True
        )

    def list_keys(self, server: str) -> list[str]:
        # 'security dump-keychain' is slow and hard to parse, but we can try to filter
        # Better: list all items and filter by service prefix
        try:
            result = subprocess.run(
                ["security", "dump-keychain"],
                capture_output=True,
                text=True
            )
            keys = []
            current_service = None
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith('0x00000007 <blob>='):
                    # This is usually where the service name is
                    parts = line.split('"')
                    if len(parts) >= 2:
                        current_service = parts[1]
                        prefix = f"{self.SERVICE_PREFIX}/{server}/"
                        if current_service.startswith(prefix):
                            keys.append(current_service[len(prefix):])
            return sorted(list(set(keys)))
        except Exception:
            return []

class EncryptedFileVault(VaultStore):
    def __init__(self, path: Path):
        self.path = path
        self.key = self._get_encryption_key()
        self.fernet = Fernet(self.key) if CRYPTOGRAPHY_AVAILABLE else None

    def _get_encryption_key(self) -> bytes:
        env_key = os.environ.get("OSTWIN_VAULT_KEY")
        if env_key:
            try:
                # Fernet key must be 32 bytes and base64 encoded
                return base64.urlsafe_b64encode(env_key.encode().ljust(32)[:32])
            except Exception:
                pass
        
        # Default key (insecure, but better than plaintext if cryptography is available)
        # Must be 32 bytes and base64 encoded
        return base64.urlsafe_b64encode(b"ostwin-default-insecure-key-32ch")

    def _load_data(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, "rb") as f:
                encrypted_data = f.read()
            if not encrypted_data:
                return {}
            if self.fernet:
                decrypted_data = self.fernet.decrypt(encrypted_data)
                return json.loads(decrypted_data)
            else:
                # Fallback to plaintext if cryptography is missing (NOT RECOMMENDED)
                return json.loads(encrypted_data)
        except Exception:
            return {}

    def _save_data(self, data: dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        json_data = json.dumps(data).encode()
        if self.fernet:
            encrypted_data = self.fernet.encrypt(json_data)
            with open(self.path, "wb") as f:
                f.write(encrypted_data)
        else:
            with open(self.path, "wb") as f:
                f.write(json_data)

    def set(self, server: str, key: str, value: str):
        data = self._load_data()
        if server not in data:
            data[server] = {}
        data[server][key] = value
        self._save_data(data)

    def get(self, server: str, key: str) -> str:
        data = self._load_data()
        return data.get(server, {}).get(key)

    def delete(self, server: str, key: str):
        data = self._load_data()
        if server in data and key in data[server]:
            del data[server][key]
            self._save_data(data)

    def list_keys(self, server: str) -> list[str]:
        data = self._load_data()
        return sorted(list(data.get(server, {}).keys()))

def get_vault() -> VaultStore:
    if sys.platform == "darwin":
        return MacOSKeychainVault()
    
    ostwin_home = Path(os.environ.get("OSTWIN_HOME", str(Path.home() / ".ostwin"))).expanduser()
    vault_path = ostwin_home / "mcp" / ".vault.enc"
    return EncryptedFileVault(vault_path)

if __name__ == "__main__":
    # Simple CLI test
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["set", "get", "delete", "list"])
    parser.add_argument("server", nargs="?")
    parser.add_argument("key", nargs="?")
    parser.add_argument("value", nargs="?")
    args = parser.parse_args()

    vault = get_vault()
    if args.action == "set" and args.server and args.key and args.value:
        vault.set(args.server, args.key, args.value)
        print(f"Set {args.server}/{args.key}")
    elif args.action == "get" and args.server and args.key:
        print(vault.get(args.server, args.key))
    elif args.action == "delete" and args.server and args.key:
        vault.delete(args.server, args.key)
        print(f"Deleted {args.server}/{args.key}")
    elif args.action == "list" and args.server:
        print("\n".join(vault.list_keys(args.server)))
