"""Brand tokens manager — loads brand.json and provides drawing primitives."""

import json
import math
import os
from pathlib import Path

from reportlab.lib.colors import HexColor, white, Color


class BrandTokens:
    """Load and expose brand tokens from a JSON file.

    Provides:
        - Named colors as HexColor objects
        - Gradient computation
        - Logo dot drawing
        - Font access
    """

    # Fallback defaults when no brand file is provided
    _DEFAULTS = {
        "name": "Report",
        "registered": False,
        "colors": {
            "navy": "#1B2D4F", "dark_blue": "#1E3F7A",
            "mid_blue": "#3375B5", "teal": "#38A3A5",
            "light_bg": "#F5F7FA", "white": "#FFFFFF",
            "medium_gray": "#6B7280", "light_gray": "#E5E7EB",
            "dark_text": "#111827", "accent_red": "#DC2626",
            "accent_green": "#16A34A",
        },
        "gradient": {
            "stops": [
                {"offset": 0.0, "color": "#38A3A5"},
                {"offset": 0.55, "color": "#3375B5"},
                {"offset": 1.0, "color": "#1E3F7A"},
            ],
            "vector": {"x1": 8, "y1": 220, "x2": 232, "y2": 20},
        },
        "logo": {"viewbox": [0, 0, 240, 240], "clip_circle": {"cx": 120, "cy": 120, "r": 112}, "dots": []},
        "fonts": {
            "primary": "Helvetica", "primary_bold": "Helvetica-Bold",
            "monospace": "Courier",
            "font_stack": "Helvetica, Arial, sans-serif",
        },
        "footer": {"left": "Confidential", "right": ""},
    }

    def __init__(self, brand_path=None):
        """Load tokens from a JSON file, or fall back to defaults.

        Args:
            brand_path: Path to a brand.json file. If None, searches for
                        brand.json next to this module, then uses defaults.
        """
        data = None
        if brand_path:
            p = Path(brand_path)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
        if data is None:
            default_path = Path(__file__).parent / "brand.json"
            if default_path.exists():
                data = json.loads(default_path.read_text(encoding="utf-8"))
        if data is None:
            data = dict(self._DEFAULTS)

        self._data = data
        self._build_colors()
        self._build_gradient()
        self._build_logo()

    # ── Public API ───────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._data.get("name", "Report")

    @property
    def registered(self) -> bool:
        return self._data.get("registered", False)

    @property
    def fonts(self) -> dict:
        return self._data.get("fonts", self._DEFAULTS["fonts"])

    @property
    def footer(self) -> dict:
        return self._data.get("footer", self._DEFAULTS["footer"])

    # ── Colors ───────────────────────────────────────────────────────

    def color(self, name: str) -> HexColor:
        """Return a named color. Falls back to dark_text if unknown."""
        return self._colors.get(name, self._colors.get("dark_text", HexColor("#111827")))

    def _build_colors(self):
        raw = self._data.get("colors", self._DEFAULTS["colors"])
        self._colors = {k: HexColor(v) for k, v in raw.items()}

    # ── Gradient ─────────────────────────────────────────────────────

    def gradient_color(self, cx: float, cy: float) -> Color:
        """Compute gradient color for a point based on the brand gradient vector."""
        vec = self._grad_vec
        dx, dy = vec["x2"] - vec["x1"], vec["y2"] - vec["y1"]
        length_sq = dx * dx + dy * dy
        if length_sq == 0:
            return self._grad_stop_colors[0]
        t = ((cx - vec["x1"]) * dx + (cy - vec["y1"]) * dy) / length_sq
        t = max(0.0, min(1.0, t))
        return self._interpolate_stops(t)

    def gradient_color_linear(self, t: float) -> Color:
        """Return gradient color for a linear parameter t in [0, 1]."""
        t = max(0.0, min(1.0, t))
        return self._interpolate_stops(t)

    def _build_gradient(self):
        grad = self._data.get("gradient", self._DEFAULTS["gradient"])
        self._grad_vec = grad.get("vector", self._DEFAULTS["gradient"]["vector"])
        stops = grad.get("stops", self._DEFAULTS["gradient"]["stops"])
        self._grad_stops = [(s["offset"], s["color"]) for s in stops]
        self._grad_stop_colors = [HexColor(s["color"]) for s in stops]

    def _interpolate_stops(self, t: float) -> Color:
        """Interpolate between gradient stops."""
        stops = self._grad_stops
        # Find the two surrounding stops
        for i in range(len(stops) - 1):
            off_a, hex_a = stops[i]
            off_b, hex_b = stops[i + 1]
            if t <= off_b:
                span = off_b - off_a
                f = (t - off_a) / span if span > 0 else 0.0
                ca, cb = HexColor(hex_a), HexColor(hex_b)
                r = ca.red + (cb.red - ca.red) * f
                g = ca.green + (cb.green - ca.green) * f
                b = ca.blue + (cb.blue - ca.blue) * f
                return Color(r, g, b)
        # Past the last stop
        return HexColor(stops[-1][1])

    # ── Logo Drawing ─────────────────────────────────────────────────

    def _build_logo(self):
        logo = self._data.get("logo", self._DEFAULTS["logo"])
        self._logo_dots = [tuple(d) for d in logo.get("dots", [])]
        clip = logo.get("clip_circle", {"cx": 120, "cy": 120, "r": 112})
        self._clip_cx, self._clip_cy, self._clip_r = clip["cx"], clip["cy"], clip["r"]
        vb = logo.get("viewbox", [0, 0, 240, 240])
        self._vb_w, self._vb_h = vb[2], vb[3]

    def draw_logo(self, canvas, x: float, y: float, size: float = 60):
        """Draw the dotted globe logo at (x, y) bottom-left corner.

        Args:
            canvas: ReportLab Canvas object.
            x, y: Bottom-left position in points.
            size: Width/height of the logo in points.
        """
        if not self._logo_dots:
            return
        scale = size / self._vb_w
        canvas.saveState()
        for cx, cy, r in self._logo_dots:
            dist = math.sqrt((cx - self._clip_cx) ** 2 + (cy - self._clip_cy) ** 2)
            if dist > self._clip_r + r:
                continue
            px = x + cx * scale
            py = y + (self._vb_h - cy) * scale  # flip Y
            pr = r * scale
            color = self.gradient_color(cx, cy)
            canvas.setFillColor(color)
            canvas.circle(px, py, pr, fill=1, stroke=0)
        canvas.restoreState()

    def draw_brand_mark(self, canvas, x: float, y: float,
                        logo_size: float = 50, font_size: float = 32):
        """Draw logo + brand name wordmark together."""
        self.draw_logo(canvas, x, y, logo_size)
        text_x = x + logo_size + 16
        text_y = y + logo_size * 0.28
        canvas.setFont(self.fonts["primary_bold"], font_size)
        canvas.setFillColor(self.color("navy"))
        canvas.drawString(text_x, text_y, self.name)
        if self.registered:
            reg_x = text_x + canvas.stringWidth(self.name, self.fonts["primary_bold"], font_size) + 2
            canvas.setFont(self.fonts["primary"], font_size * 0.35)
            canvas.setFillColor(Color(
                self.color("navy").red,
                self.color("navy").green,
                self.color("navy").blue,
                0.5,
            ))
            canvas.drawString(reg_x, text_y + font_size * 0.55, "\u00AE")

    # ── Gradient Bar Drawing ─────────────────────────────────────────

    def draw_gradient_bar(self, canvas, x: float, y: float,
                          width: float, height: float, steps: int = 100):
        """Draw a horizontal gradient bar."""
        step_w = width / steps
        for i in range(steps):
            t = i / steps
            color = self.gradient_color_linear(t)
            canvas.setFillColor(color)
            canvas.rect(x + i * step_w, y, step_w + 0.5, height, fill=1, stroke=0)
