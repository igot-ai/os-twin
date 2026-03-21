"""
Reporter — composable, data-driven PDF report engine for Agent OS.

Usage:
    from reporter import ReportEngine
    engine = ReportEngine("brand.json")
    engine.generate("spec.json", "output.pdf")

CLI:
    python -m reporter generate spec.json -o output.pdf
    python -m reporter validate spec.json
    python -m reporter list-components
"""

from .engine import ReportEngine, generate_report
from .brand import BrandTokens

__all__ = ["ReportEngine", "generate_report", "BrandTokens"]
__version__ = "1.0.0"
