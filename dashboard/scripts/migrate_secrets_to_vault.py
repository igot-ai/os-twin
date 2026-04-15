#!/usr/bin/env python3
"""
Migrate plaintext secrets from env files into the vault.

Usage:
    python -m dashboard.scripts.migrate_secrets_to_vault [--dry-run]

For each known secret key the script:
  1. Reads the plaintext value from the source file.
  2. Stores it in the appropriate vault scope.
  3. Replaces the plaintext value in the source with a ${vault:scope/key} ref.
  4. Backs up the original file as <name>.pre-vault.bak.

The script is idempotent: if a value is already a vault ref it is skipped.
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure project root is importable
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


# ── Migration map ────────────────────────────────────────────────────────

MIGRATION_MAP: Dict[str, Tuple[str, str]] = {
    # env_key -> (vault_scope, vault_key)
    "ANTHROPIC_API_KEY":  ("providers", "anthropic"),
    "OPENAI_API_KEY":     ("providers", "openai"),
    "GOOGLE_API_KEY":     ("providers", "google"),
    "TELEGRAM_BOT_TOKEN": ("channels", "telegram"),
    "DISCORD_TOKEN":      ("channels", "discord"),
    "NGROK_AUTHTOKEN":    ("tunnel", "ngrok"),
    "OSTWIN_API_KEY":     ("auth", "dashboard"),
}

VAULT_REF_RE = re.compile(r"^\$\{vault:[^}]+\}$")


# ── Helpers ──────────────────────────────────────────────────────────────

def _is_vault_ref(value: str) -> bool:
    return bool(VAULT_REF_RE.match(value.strip()))


def _vault_ref(scope: str, key: str) -> str:
    return f"${{vault:{scope}/{key}}}"


def _backup(path: Path, dry_run: bool) -> None:
    bak = path.with_suffix(path.suffix + ".pre-vault.bak")
    if bak.exists():
        return  # already backed up
    if dry_run:
        print(f"  [dry-run] would back up {path} -> {bak.name}")
    else:
        shutil.copy2(path, bak)
        print(f"  backed up {path} -> {bak.name}")


# ── .env file processing ────────────────────────────────────────────────

def _parse_env_file(path: Path) -> List[Tuple[str, str]]:
    """Parse KEY=VALUE lines, ignoring comments and blanks."""
    pairs = []
    if not path.exists():
        return pairs
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Strip optional surrounding quotes
        value = value.strip().strip("'\"")
        pairs.append((key.strip(), value))
    return pairs


def _migrate_env_file(
    path: Path,
    vault,
    dry_run: bool,
) -> int:
    """Migrate secrets in a .env file. Returns count migrated."""
    if not path.exists():
        print(f"  skipping {path} (not found)")
        return 0

    pairs = _parse_env_file(path)
    count = 0
    new_lines: List[str] = []

    for key, value in pairs:
        scope_key = MIGRATION_MAP.get(key)
        if scope_key is None:
            new_lines.append(f"{key}={value}")
            continue

        scope, vkey = scope_key
        ref = _vault_ref(scope, vkey)

        if _is_vault_ref(value):
            print(f"  {key}: already a vault ref, skipping")
            new_lines.append(f"{key}={value}")
            continue

        if not value:
            print(f"  {key}: empty value, skipping")
            new_lines.append(f"{key}={value}")
            continue

        if dry_run:
            print(f"  [dry-run] {key} -> vault:{scope}/{vkey}")
        else:
            vault.set(scope, vkey, value)
            print(f"  {key} -> vault:{scope}/{vkey}")

        new_lines.append(f"{key}={ref}")
        count += 1

    if count > 0:
        _backup(path, dry_run)
        if not dry_run:
            path.write_text("\n".join(new_lines) + "\n")

    return count


# ── JSON file processing ────────────────────────────────────────────────

def _migrate_json_file(
    path: Path,
    vault,
    key_field: str,
    scope: str,
    vkey: str,
    dry_run: bool,
) -> int:
    """Migrate a single secret field inside a JSON file."""
    if not path.exists():
        print(f"  skipping {path} (not found)")
        return 0

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  error reading {path}: {exc}")
        return 0

    # Walk top-level keys looking for key_field
    value = _deep_get(data, key_field)
    if value is None or _is_vault_ref(str(value)):
        return 0

    ref = _vault_ref(scope, vkey)

    if dry_run:
        print(f"  [dry-run] {path}:{key_field} -> vault:{scope}/{vkey}")
    else:
        vault.set(scope, vkey, str(value))
        _deep_set(data, key_field, ref)
        _backup(path, dry_run)
        path.write_text(json.dumps(data, indent=2))
        print(f"  {path}:{key_field} -> vault:{scope}/{vkey}")

    return 1


def _deep_get(data, dotpath: str):
    parts = dotpath.split(".")
    for p in parts:
        if isinstance(data, dict) and p in data:
            data = data[p]
        else:
            return None
    return data


def _deep_set(data, dotpath: str, value):
    parts = dotpath.split(".")
    for p in parts[:-1]:
        data = data.setdefault(p, {})
    data[parts[-1]] = value


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate plaintext secrets into the vault."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing.",
    )
    args = parser.parse_args()

    from dashboard.lib.settings.vault import get_vault

    vault = get_vault()

    total = 0
    env_path = Path.home() / ".ostwin" / ".env"

    print(f"\n=== Migrating {env_path} ===")
    total += _migrate_env_file(env_path, vault, args.dry_run)

    # channels.json: bot_token fields
    channels_path = Path.home() / ".ostwin" / "channels.json"
    if channels_path.exists():
        print(f"\n=== Migrating {channels_path} ===")
        total += _migrate_json_file(
            channels_path, vault,
            "telegram.bot_token", "channels", "telegram",
            args.dry_run,
        )
        total += _migrate_json_file(
            channels_path, vault,
            "discord.token", "channels", "discord",
            args.dry_run,
        )

    print(f"\n{'[dry-run] ' if args.dry_run else ''}Migrated {total} secret(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
