#!/usr/bin/env bash
# Validate subcommands.json against subcommands-schema.json using Python's jsonschema

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <path-to-subcommands.json>" >&2
    exit 1
fi

MANIFEST_PATH="$1"
SCHEMA_PATH="$(dirname "$0")/../schemas/subcommands-schema.json"

if [ ! -f "$MANIFEST_PATH" ]; then
    echo "Error: Manifest file not found: $MANIFEST_PATH" >&2
    exit 1
fi

if [ ! -f "$SCHEMA_PATH" ]; then
    echo "Error: Schema file not found: $SCHEMA_PATH" >&2
    exit 1
fi

# Use Python to validate
export MANIFEST_PATH
export SCHEMA_PATH

python3 -c "
import json
import sys
import os
from jsonschema import validate, ValidationError

manifest_path = os.environ.get('MANIFEST_PATH')
schema_path = os.environ.get('SCHEMA_PATH')

try:
    if not schema_path or not os.path.isfile(schema_path):
        print(f'Error: Schema file not found: {schema_path}', file=sys.stderr)
        sys.exit(1)
    if not manifest_path or not os.path.isfile(manifest_path):
        print(f'Error: Manifest file not found: {manifest_path}', file=sys.stderr)
        sys.exit(1)

    with open(schema_path, 'r') as sf:
        schema = json.load(sf)
    with open(manifest_path, 'r') as mf:
        instance = json.load(mf)
    validate(instance=instance, schema=schema)
    print(f'Valid: {manifest_path}')
    sys.exit(0)
except ValidationError as e:
    print(f'Invalid: {manifest_path}', file=sys.stderr)
    print(e.message, file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
"
