"""
ReportEngine — processes a JSON spec and generates a PDF.

The spec defines metadata and an ordered list of pages, each dispatched
to a registered component from components.py.
"""

import json
from pathlib import Path

from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas

from .brand import BrandTokens
from . import components as comp


PAGE_SIZES = {
    "A4": A4,
    "letter": letter,
}


class ReportEngine:
    """Data-driven PDF report generator.

    Usage:
        engine = ReportEngine()
        engine.generate("spec.json", "output.pdf")

    Or from a dict:
        engine = ReportEngine(brand_path="brand.json")
        engine.generate_from_dict(spec_dict, "output.pdf")
    """

    def __init__(self, brand_path=None):
        """Initialize with optional brand tokens file.

        Args:
            brand_path: Path to brand.json. If None, uses the default
                        bundled with the reporter package.
        """
        self._default_brand_path = brand_path

    def generate(self, spec_path, output_path=None):
        """Generate a PDF from a spec JSON file.

        Args:
            spec_path: Path to the report spec JSON.
            output_path: Where to write the PDF. If None, derives from spec.

        Returns:
            Path to the generated PDF.
        """
        spec_path = Path(spec_path)
        spec = json.loads(spec_path.read_text(encoding="utf-8"))

        if output_path is None:
            output_path = spec.get("output", spec_path.stem + ".pdf")

        return self.generate_from_dict(spec, str(output_path), base_dir=spec_path.parent)

    def generate_from_dict(self, spec, output_path, base_dir=None):
        """Generate a PDF from a spec dictionary.

        Args:
            spec: Report specification dict.
            output_path: Where to write the PDF.
            base_dir: Base directory for resolving relative paths.

        Returns:
            Path to the generated PDF.
        """
        # Resolve brand
        brand_path = self._default_brand_path
        if "brand_file" in spec and base_dir:
            candidate = Path(base_dir) / spec["brand_file"]
            if candidate.exists():
                brand_path = str(candidate)
        brand = BrandTokens(brand_path)

        # Resolve page size
        page_size = PAGE_SIZES.get(spec.get("page_size", "A4"), A4)
        W, H = page_size

        # Create canvas
        c = canvas.Canvas(str(output_path), pagesize=page_size)
        c.setTitle(spec.get("title", "Report"))
        c.setAuthor(spec.get("author", brand.name))
        if spec.get("subject"):
            c.setSubject(spec["subject"])

        # Process pages
        pages = spec.get("pages", [])
        page_num = 1

        for page_spec in pages:
            page_type = page_spec.get("type")
            if not page_type:
                continue

            component_cls = comp.get_component(page_type)
            if component_cls is None:
                print(f"[reporter] Warning: unknown page type '{page_type}', skipping")
                continue

            component = component_cls(page_spec)
            component.render(c, brand, W, H, page_num=page_num)
            page_num += 1

        c.save()
        print(f"[reporter] PDF generated: {output_path}  ({page_num - 1} pages)")
        return output_path

    @staticmethod
    def validate_spec(spec_path):
        """Validate a report spec file. Returns (is_valid, errors)."""
        errors = []
        try:
            spec_path = Path(spec_path)
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {e}"]
        except FileNotFoundError:
            return False, [f"File not found: {spec_path}"]

        if "pages" not in spec:
            errors.append("Missing 'pages' array")
        elif not isinstance(spec["pages"], list):
            errors.append("'pages' must be an array")
        else:
            for i, page in enumerate(spec["pages"]):
                if "type" not in page:
                    errors.append(f"Page {i}: missing 'type' field")
                elif comp.get_component(page["type"]) is None:
                    errors.append(f"Page {i}: unknown component type '{page['type']}'")

        return len(errors) == 0, errors


def generate_report(spec_path, output_path=None, brand_path=None):
    """Convenience function to generate a report in one call."""
    engine = ReportEngine(brand_path=brand_path)
    return engine.generate(spec_path, output_path)
