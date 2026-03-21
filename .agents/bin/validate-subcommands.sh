#!/bin/bash
# validate-subcommands.sh - Validate subcommands.json against its schema.

MANIFEST_PATH="$1"
# Schema is relative to this script: bin/../schemas/subcommands-schema.json
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_PATH="$SCRIPT_DIR/../schemas/subcommands-schema.json"

if [ -z "$MANIFEST_PATH" ]; then
    echo "Usage: $0 <manifest-path>" >&2
    exit 1
fi

if [ ! -f "$MANIFEST_PATH" ]; then
    echo "Error: Manifest file not found: $MANIFEST_PATH" >&2
    exit 1
fi

python3 -c "
import sys
import json
import jsonschema

schema_path = '$SCHEMA_PATH'
manifest_path = '$MANIFEST_PATH'

try:
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    jsonschema.validate(instance=manifest, schema=schema)
    print(f'Valid: {manifest_path}')
    sys.exit(0)
except jsonschema.exceptions.ValidationError as e:
    print(f'Validation error in {manifest_path}: {e.message}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'Error: {str(e)}', file=sys.stderr)
    sys.exit(1)
"

