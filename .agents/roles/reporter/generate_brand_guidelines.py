#!/usr/bin/env python3
"""Generate igot.ai Brand Guidelines PDF.

This is a backward-compatible wrapper that invokes the report engine
with the brand-guidelines-spec.json spec file.

Original: 715-line monolithic script
Now: thin wrapper around the composable report engine
"""

import os
import sys

# The reporter package is the directory this script lives in.
# We need to add the PARENT directory so `reporter` is importable as a package.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from reporter.engine import ReportEngine


def main():
    spec_path = os.path.join(_this_dir, "brand-guidelines-spec.json")
    engine = ReportEngine()
    engine.generate(spec_path)


if __name__ == "__main__":
    main()
