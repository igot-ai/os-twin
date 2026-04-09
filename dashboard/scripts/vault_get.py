#!/usr/bin/env python3
"""CLI one-liner for the bash shim (.agents/lib/resolve-vault.sh).

Usage:
    python -m dashboard.scripts.vault_get <scope> <key>

Prints the secret to stdout.  Exits 1 if the secret is not set.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so dashboard imports work
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <scope> <key>", file=sys.stderr)
        return 2

    scope, key = sys.argv[1], sys.argv[2]

    try:
        from dashboard.lib.settings.vault import get_vault

        vault = get_vault()
        value = vault.get(scope, key)
    except Exception as exc:
        print(f"vault error: {exc}", file=sys.stderr)
        return 1

    if value is None:
        print(f"secret not set: {scope}/{key}", file=sys.stderr)
        return 1

    # Print raw value (no trailing newline for piping)
    sys.stdout.write(value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
