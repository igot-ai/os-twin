"""
CLI entry point for the reporter package.

Usage:
    python -m reporter generate spec.json [-o output.pdf] [--brand brand.json]
    python -m reporter validate spec.json
    python -m reporter list-components
"""

import argparse
import sys

from .engine import ReportEngine
from .components import list_components


def main():
    parser = argparse.ArgumentParser(
        prog="reporter",
        description="Composable PDF report engine for Agent OS",
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # ── generate ──
    gen = sub.add_parser("generate", help="Generate a PDF from a report spec")
    gen.add_argument("spec", help="Path to report spec JSON file")
    gen.add_argument("-o", "--output", help="Output PDF path (default: <spec-stem>.pdf)")
    gen.add_argument("--brand", help="Path to brand.json (default: bundled)")

    # ── validate ──
    val = sub.add_parser("validate", help="Validate a report spec without generating")
    val.add_argument("spec", help="Path to report spec JSON file")

    # ── list-components ──
    sub.add_parser("list-components", help="List all available page component types")

    args = parser.parse_args()

    if args.command == "generate":
        engine = ReportEngine(brand_path=args.brand)
        try:
            output = engine.generate(args.spec, args.output)
            print(f"✅ Report generated: {output}")
        except Exception as e:
            print(f"❌ Generation failed: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "validate":
        is_valid, errors = ReportEngine.validate_spec(args.spec)
        if is_valid:
            print("✅ Spec is valid")
        else:
            print("❌ Validation errors:")
            for err in errors:
                print(f"   • {err}")
            sys.exit(1)

    elif args.command == "list-components":
        comps = list_components()
        print(f"Available page components ({len(comps)}):\n")
        for name, doc in comps:
            print(f"  {name:20s}  {doc}")
        print()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
