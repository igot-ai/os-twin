"""
Composable page components for the report engine.

Each component is a class with a `render(canvas, brand, page_width, page_height)` method.
Components are instantiated from their section in the report spec JSON.
"""

import math
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, Color, white


# ═══════════════════════════════════════════════════════════════════
# Base helpers
# ═══════════════════════════════════════════════════════════════════

def draw_page_header(c, brand, W, H, title, subtitle=None, page_num=None):
    """Draw consistent page header with top bar, title, and divider."""
    c.setFillColor(brand.color("navy"))
    c.rect(0, H - 8 * mm, W, 8 * mm, fill=1, stroke=0)
    if page_num:
        c.setFillColor(white)
        c.setFont(brand.fonts["primary"], 8)
        c.drawRightString(W - 20 * mm, H - 6 * mm, f"{page_num:02d}")
    c.setFillColor(brand.color("navy"))
    c.setFont(brand.fonts["primary_bold"], 28)
    c.drawString(30 * mm, H - 40 * mm, title)
    if subtitle:
        c.setFillColor(brand.color("medium_gray"))
        c.setFont(brand.fonts["primary"], 11)
        c.drawString(30 * mm, H - 50 * mm, subtitle)
    c.setStrokeColor(brand.color("light_gray"))
    c.setLineWidth(0.5)
    c.line(30 * mm, H - 55 * mm, W - 30 * mm, H - 55 * mm)


def draw_footer(c, brand, W, H):
    """Draw page footer with line and text."""
    c.setStrokeColor(brand.color("light_gray"))
    c.setLineWidth(0.5)
    c.line(30 * mm, 20 * mm, W - 30 * mm, 20 * mm)
    c.setFillColor(brand.color("medium_gray"))
    c.setFont(brand.fonts["primary"], 7)
    footer = brand.footer
    c.drawString(30 * mm, 15 * mm, footer.get("left", ""))
    c.drawRightString(W - 30 * mm, 15 * mm, footer.get("right", ""))


# ═══════════════════════════════════════════════════════════════════
# Component registry
# ═══════════════════════════════════════════════════════════════════

_REGISTRY = {}


def register(name):
    """Decorator to register a component class by type name."""
    def _wrap(cls):
        _REGISTRY[name] = cls
        return cls
    return _wrap


def get_component(name):
    """Look up a registered component by name."""
    return _REGISTRY.get(name)


def list_components():
    """Return list of (name, docstring) for all registered components."""
    return [(name, (cls.__doc__ or "").strip().split("\n")[0])
            for name, cls in sorted(_REGISTRY.items())]


# ═══════════════════════════════════════════════════════════════════
# Cover Page
# ═══════════════════════════════════════════════════════════════════

@register("cover")
class CoverPage:
    """Full-bleed cover page with navy background, logo, and title."""

    def __init__(self, spec: dict):
        self.title = spec.get("title", "Report")
        self.subtitle = spec.get("subtitle", "")
        self.version_line = spec.get("version_line", "")

    def render(self, c, brand, W, H, **kw):
        c.setFillColor(brand.color("navy"))
        c.rect(0, 0, W, H, fill=1, stroke=0)
        # Accent bar
        c.setFillColor(brand.color("mid_blue"))
        c.rect(0, H - 6 * mm, W, 6 * mm, fill=1, stroke=0)
        c.setFillColor(brand.color("teal"))
        c.rect(0, H - 6 * mm, W * 0.4, 6 * mm, fill=1, stroke=0)
        # Logo
        logo_size = 120
        logo_x = (W - logo_size) / 2
        logo_y = H * 0.52
        brand.draw_logo(c, logo_x, logo_y, logo_size)
        # Title
        c.setFont(brand.fonts["primary_bold"], 52)
        c.setFillColor(white)
        tw = c.stringWidth(self.title, brand.fonts["primary_bold"], 52)
        c.drawString((W - tw) / 2, logo_y - 50, self.title)
        # ® if applicable
        if brand.registered:
            c.setFont(brand.fonts["primary"], 16)
            c.setFillColor(Color(1, 1, 1, 0.6))
            c.drawString((W + tw) / 2 + 4, logo_y - 50 + 32, "\u00AE")
        # Subtitle
        if self.subtitle:
            c.setFont(brand.fonts["primary"], 16)
            c.setFillColor(Color(1, 1, 1, 0.7))
            sw = c.stringWidth(self.subtitle, brand.fonts["primary"], 16)
            c.drawString((W - sw) / 2, logo_y - 85, self.subtitle)
        # Version line
        if self.version_line:
            c.setFont(brand.fonts["primary"], 9)
            c.setFillColor(Color(1, 1, 1, 0.4))
            c.drawCentredString(W / 2, 30 * mm, self.version_line)
        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Table of Contents
# ═══════════════════════════════════════════════════════════════════

@register("toc")
class TOCPage:
    """Auto-generated table of contents from page entries."""

    def __init__(self, spec: dict):
        self.items = spec.get("items", [])
        # items: [{"num": "01", "title": "...", "desc": "..."}]

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, "Contents", page_num=page_num)
        draw_footer(c, brand, W, H)
        y = H - 80 * mm
        for item in self.items:
            num = item.get("num", "")
            title = item.get("title", "")
            desc = item.get("desc", "")
            c.setFont(brand.fonts["primary_bold"], 13)
            c.setFillColor(brand.color("teal"))
            c.drawString(30 * mm, y, str(num))
            c.setFillColor(brand.color("navy"))
            c.drawString(48 * mm, y, title)
            c.setFont(brand.fonts["primary"], 10)
            c.setFillColor(brand.color("medium_gray"))
            c.drawString(48 * mm, y - 16, desc)
            c.setStrokeColor(brand.color("light_gray"))
            c.setDash(1, 3)
            c.line(48 * mm, y - 24, W - 30 * mm, y - 24)
            c.setDash()
            y -= 42
        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Text Section
# ═══════════════════════════════════════════════════════════════════

@register("text_section")
class TextSection:
    """Page with titled text blocks — suitable for overviews and narratives."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "")
        self.subtitle = spec.get("subtitle", "")
        self.blocks = spec.get("blocks", [])
        # blocks: [{"title": "Mission", "body": "..."}]

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)
        y = H - 75 * mm
        for block in self.blocks:
            title = block.get("title", "")
            body = block.get("body", "")
            # Title
            c.setFillColor(brand.color("navy"))
            c.setFont(brand.fonts["primary_bold"], 14)
            c.drawString(30 * mm, y, title)
            y -= 8
            # Accent line
            c.setStrokeColor(brand.color("teal"))
            c.setLineWidth(2)
            c.line(30 * mm, y, 55 * mm, y)
            c.setLineWidth(0.5)
            y -= 16
            # Body
            c.setFillColor(brand.color("dark_text"))
            c.setFont(brand.fonts["primary"], 10.5)
            for line in body.split("\n"):
                c.drawString(30 * mm, y, line.strip())
                y -= 15
            y -= 20
            # Page break if running low
            if y < 60 * mm:
                c.showPage()
                draw_page_header(c, brand, W, H, self.heading + " (cont.)", page_num=page_num)
                draw_footer(c, brand, W, H)
                y = H - 75 * mm
        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Color Palette
# ═══════════════════════════════════════════════════════════════════

@register("color_palette")
class ColorPalette:
    """Color swatch page with hex codes and usage labels."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "Color Palette")
        self.subtitle = spec.get("subtitle", "")
        self.primary = spec.get("primary", [])
        self.secondary = spec.get("secondary", [])
        self.show_gradient = spec.get("show_gradient", False)
        # primary/secondary: [{"name": "...", "hex": "#...", "usage": "..."}]

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)
        y = H - 75 * mm

        # Primary
        if self.primary:
            c.setFont(brand.fonts["primary_bold"], 12)
            c.setFillColor(brand.color("navy"))
            c.drawString(30 * mm, y, "Primary Colors")
            y -= 25
            swatch_w = (W - 60 * mm - 15 * mm) / max(len(self.primary), 1)
            sx = 30 * mm
            for item in self.primary:
                hex_val = item.get("hex", "#000000")
                c.setFillColor(HexColor(hex_val))
                c.roundRect(sx, y - 38 * mm, swatch_w, 30 * mm, 5, fill=1, stroke=0)
                c.setFont(brand.fonts["primary_bold"], 9)
                c.setFillColor(brand.color("navy"))
                c.drawString(sx, y - 44 * mm, item.get("name", ""))
                c.setFont(brand.fonts["primary"], 8.5)
                c.setFillColor(brand.color("medium_gray"))
                c.drawString(sx, y - 50 * mm, hex_val.upper())
                usage = item.get("usage", "")
                c.setFont(brand.fonts["primary"], 7.5)
                for i, line in enumerate(usage.split("\n")):
                    c.drawString(sx, y - 56 * mm - i * 10, line)
                sx += swatch_w + 5 * mm
            y -= 78 * mm

        # Secondary
        if self.secondary:
            c.setFont(brand.fonts["primary_bold"], 12)
            c.setFillColor(brand.color("navy"))
            c.drawString(30 * mm, y, "Secondary & Neutral Colors")
            y -= 20
            swatch_w = (W - 60 * mm - 15 * mm) / max(len(self.secondary), 1)
            sx = 30 * mm
            for item in self.secondary:
                hex_val = item.get("hex", "#000000")
                c.setFillColor(HexColor(hex_val))
                needs_border = item.get("border", False)
                if needs_border:
                    c.setStrokeColor(brand.color("light_gray"))
                    c.roundRect(sx, y - 22 * mm, swatch_w, 18 * mm, 4, fill=1, stroke=1)
                else:
                    c.roundRect(sx, y - 22 * mm, swatch_w, 18 * mm, 4, fill=1, stroke=0)
                c.setFont(brand.fonts["primary_bold"], 9)
                c.setFillColor(brand.color("navy"))
                c.drawString(sx, y - 28 * mm, item.get("name", ""))
                c.setFont(brand.fonts["primary"], 8.5)
                c.setFillColor(brand.color("medium_gray"))
                c.drawString(sx, y - 34 * mm, hex_val.upper())
                sx += swatch_w + 5 * mm
            y -= 55 * mm

        # Gradient bar
        if self.show_gradient:
            c.setFont(brand.fonts["primary_bold"], 12)
            c.setFillColor(brand.color("navy"))
            c.drawString(30 * mm, y, "Brand Gradient")
            y -= 18
            bar_w = W - 60 * mm
            bar_h = 16 * mm
            brand.draw_gradient_bar(c, 30 * mm, y - bar_h, bar_w, bar_h)
            c.setFont(brand.fonts["primary"], 8)
            c.setFillColor(brand.color("medium_gray"))
            c.drawString(30 * mm, y - bar_h - 12, "#38A3A5  (0%)")
            c.drawCentredString(W / 2, y - bar_h - 12, "#3375B5  (55%)")
            c.drawRightString(W - 30 * mm, y - bar_h - 12, "#1E3F7A  (100%)")

        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Typography
# ═══════════════════════════════════════════════════════════════════

@register("typography")
class TypographyPage:
    """Font specimen page with type scale and weight guidance."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "Typography")
        self.subtitle = spec.get("subtitle", "")
        self.font_stack = spec.get("font_stack", "")
        self.scales = spec.get("scales", [])
        self.weights = spec.get("weights", [])
        # scales: [{"label": "H1", "font": "...", "size": 28, "usage": "..."}]
        # weights: [{"name": "Bold (700)", "desc": "Headings..."}]

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)
        y = H - 75 * mm

        # Font stack
        if self.font_stack:
            c.setFont(brand.fonts["primary_bold"], 12)
            c.setFillColor(brand.color("navy"))
            c.drawString(30 * mm, y, "Primary Typeface")
            y -= 30
            c.setFillColor(brand.color("light_bg"))
            c.roundRect(30 * mm, y - 30 * mm, W - 60 * mm, 35 * mm, 6, fill=1, stroke=0)
            c.setFont(brand.fonts["primary"], 9)
            c.setFillColor(brand.color("medium_gray"))
            c.drawString(35 * mm, y, "Font Stack")
            c.setFont(brand.fonts["monospace"], 9)
            c.setFillColor(brand.color("dark_text"))
            lines = self.font_stack.split("\n") if "\n" in self.font_stack else [self.font_stack]
            for i, line in enumerate(lines):
                c.drawString(35 * mm, y - 14 - i * 12, line)
            y -= 50 * mm

        # Type scale
        if self.scales:
            c.setFont(brand.fonts["primary_bold"], 12)
            c.setFillColor(brand.color("navy"))
            c.drawString(30 * mm, y, "Type Scale")
            y -= 25
            for item in self.scales:
                font = item.get("font", brand.fonts["primary_bold"])
                size = min(item.get("size", 14), 30)
                c.setFont(font, size)
                c.setFillColor(brand.color("navy"))
                c.drawString(30 * mm, y, brand.name)
                c.setFont(brand.fonts["primary"], 8)
                c.setFillColor(brand.color("teal"))
                c.drawString(90 * mm, y + 4, item.get("label", ""))
                c.setFillColor(brand.color("medium_gray"))
                c.drawString(90 * mm, y - 8, f"{item.get('size', '')}px  \u2022  {item.get('usage', '')}")
                c.setStrokeColor(brand.color("light_gray"))
                c.line(30 * mm, y - 16, W - 30 * mm, y - 16)
                y -= 34

        # Weights
        if self.weights:
            y -= 10
            c.setFont(brand.fonts["primary_bold"], 12)
            c.setFillColor(brand.color("navy"))
            c.drawString(30 * mm, y, "Weight Usage")
            y -= 20
            for item in self.weights:
                c.setFont(brand.fonts["primary_bold"], 10)
                c.setFillColor(brand.color("navy"))
                c.drawString(30 * mm, y, item.get("name", ""))
                c.setFont(brand.fonts["primary"], 10)
                c.setFillColor(brand.color("medium_gray"))
                c.drawString(75 * mm, y, item.get("desc", ""))
                y -= 18

        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Logo Usage
# ═══════════════════════════════════════════════════════════════════

@register("logo_usage")
class LogoUsagePage:
    """Logo presentation page showing primary mark and icon variants."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "Logo")
        self.subtitle = spec.get("subtitle", "")

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)
        y = H - 75 * mm

        # Primary logo
        c.setFont(brand.fonts["primary_bold"], 12)
        c.setFillColor(brand.color("navy"))
        c.drawString(30 * mm, y, "Primary Logo")
        y -= 8
        c.setFont(brand.fonts["primary"], 10)
        c.setFillColor(brand.color("medium_gray"))
        c.drawString(30 * mm, y, "The preferred logo combines the globe mark with the wordmark.")
        y -= 25
        box_h = 70 * mm
        c.setFillColor(brand.color("light_bg"))
        c.roundRect(30 * mm, y - box_h + 15 * mm, W - 60 * mm, box_h, 6, fill=1, stroke=0)
        brand.draw_brand_mark(c, W / 2 - 75, y - box_h / 2 + 10 * mm, logo_size=55, font_size=36)
        y -= box_h + 5 * mm

        # Icon variants
        c.setFont(brand.fonts["primary_bold"], 12)
        c.setFillColor(brand.color("navy"))
        c.drawString(30 * mm, y, "Logo Mark (Icon)")
        y -= 8
        c.setFont(brand.fonts["primary"], 10)
        c.setFillColor(brand.color("medium_gray"))
        c.drawString(30 * mm, y, "Use the standalone mark for small applications, favicons, and app icons.")
        y -= 25
        bw = (W - 70 * mm) / 2
        box_h2 = 55 * mm
        # Light
        c.setFillColor(brand.color("light_bg"))
        c.roundRect(30 * mm, y - box_h2 + 15 * mm, bw, box_h2, 6, fill=1, stroke=0)
        brand.draw_logo(c, 30 * mm + bw / 2 - 22, y - box_h2 / 2 + 5 * mm, 44)
        c.setFont(brand.fonts["primary"], 8)
        c.setFillColor(brand.color("medium_gray"))
        c.drawCentredString(30 * mm + bw / 2, y - box_h2 + 20 * mm, "On light backgrounds")
        # Dark
        c.setFillColor(brand.color("navy"))
        c.roundRect(40 * mm + bw, y - box_h2 + 15 * mm, bw, box_h2, 6, fill=1, stroke=0)
        brand.draw_logo(c, 40 * mm + bw + bw / 2 - 22, y - box_h2 / 2 + 5 * mm, 44)
        c.setFont(brand.fonts["primary"], 8)
        c.setFillColor(Color(1, 1, 1, 0.6))
        c.drawCentredString(40 * mm + bw + bw / 2, y - box_h2 + 20 * mm, "On dark backgrounds")

        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Clear Space & Sizing
# ═══════════════════════════════════════════════════════════════════

@register("clear_space")
class ClearSpacePage:
    """Logo clear space rules and minimum sizing requirements."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "Clear Space & Sizing")
        self.subtitle = spec.get("subtitle", "")

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)
        y = H - 75 * mm

        # Clear space section
        c.setFont(brand.fonts["primary_bold"], 12)
        c.setFillColor(brand.color("navy"))
        c.drawString(30 * mm, y, "Clear Space")
        y -= 8
        c.setFont(brand.fonts["primary"], 10)
        c.setFillColor(brand.color("medium_gray"))
        c.drawString(30 * mm, y, "Maintain clear space around the logo equal to the height of the letter 'i'.")
        y -= 30
        box_w = W - 60 * mm
        box_h = 65 * mm
        c.setFillColor(brand.color("light_bg"))
        c.roundRect(30 * mm, y - box_h, box_w, box_h, 6, fill=1, stroke=0)
        cx_pt, cy_pt = W / 2, y - box_h / 2
        pad = 28
        c.setStrokeColor(brand.color("teal"))
        c.setDash(4, 4)
        c.setLineWidth(1)
        mark_w, mark_h = 160, 50
        c.rect(cx_pt - mark_w / 2 - pad, cy_pt - mark_h / 2 - pad,
               mark_w + pad * 2, mark_h + pad * 2, fill=0, stroke=1)
        c.setDash()
        c.setFont(brand.fonts["primary"], 8)
        c.setFillColor(brand.color("teal"))
        c.drawCentredString(cx_pt, cy_pt + mark_h / 2 + pad + 4, "X")
        c.drawCentredString(cx_pt, cy_pt - mark_h / 2 - pad - 12, "X")
        c.drawString(cx_pt - mark_w / 2 - pad - 12, cy_pt - 3, "X")
        c.drawString(cx_pt + mark_w / 2 + pad + 4, cy_pt - 3, "X")
        brand.draw_brand_mark(c, cx_pt - 68, cy_pt - 18, logo_size=36, font_size=24)
        y -= box_h + 15 * mm

        # Minimum sizes
        c.setFont(brand.fonts["primary_bold"], 12)
        c.setFillColor(brand.color("navy"))
        c.drawString(30 * mm, y, "Minimum Sizes")
        y -= 8
        c.setFont(brand.fonts["primary"], 10)
        c.setFillColor(brand.color("medium_gray"))
        c.drawString(30 * mm, y, "Do not reproduce the logo smaller than these minimum dimensions.")
        y -= 30
        half_w = (box_w - 10 * mm) / 2
        c.setFillColor(brand.color("light_bg"))
        c.roundRect(30 * mm, y - 40 * mm, half_w, 40 * mm, 6, fill=1, stroke=0)
        mid_x1 = 30 * mm + half_w / 2
        brand.draw_brand_mark(c, mid_x1 - 45, y - 22 * mm, logo_size=24, font_size=16)
        c.setFont(brand.fonts["primary_bold"], 9)
        c.setFillColor(brand.color("navy"))
        c.drawCentredString(mid_x1, y - 32 * mm, "Digital: 120px wide")
        c.setFont(brand.fonts["primary"], 8)
        c.setFillColor(brand.color("medium_gray"))
        c.drawCentredString(mid_x1, y - 38 * mm, "Full logo minimum")

        x2 = 30 * mm + half_w + 10 * mm
        c.setFillColor(brand.color("light_bg"))
        c.roundRect(x2, y - 40 * mm, half_w, 40 * mm, 6, fill=1, stroke=0)
        mid_x2 = x2 + half_w / 2
        brand.draw_logo(c, mid_x2 - 12, y - 24 * mm, 24)
        c.setFont(brand.fonts["primary_bold"], 9)
        c.setFillColor(brand.color("navy"))
        c.drawCentredString(mid_x2, y - 32 * mm, "Icon only: 24px / 8mm")
        c.setFont(brand.fonts["primary"], 8)
        c.setFillColor(brand.color("medium_gray"))
        c.drawCentredString(mid_x2, y - 38 * mm, "Favicon, app icon minimum")

        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Checklist (Do's & Don'ts)
# ═══════════════════════════════════════════════════════════════════

@register("checklist")
class ChecklistPage:
    """Do's and don'ts page with colored icons."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "Checklist")
        self.subtitle = spec.get("subtitle", "")
        self.dont = spec.get("dont", [])
        self.do = spec.get("do", [])
        self.do_heading = spec.get("do_heading", "Best Practices")
        self.dont_heading = spec.get("dont_heading", "")

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)
        y = H - 75 * mm

        if self.dont_heading:
            c.setFont(brand.fonts["primary"], 10)
            c.setFillColor(brand.color("medium_gray"))
            c.drawString(30 * mm, y, self.dont_heading)
            y -= 20

        for rule in self.dont:
            c.setFillColor(brand.color("accent_red"))
            c.setFont(brand.fonts["primary_bold"], 14)
            c.drawString(30 * mm, y, "\u2717")
            c.setFont(brand.fonts["primary"], 10.5)
            c.setFillColor(brand.color("dark_text"))
            c.drawString(40 * mm, y, rule)
            y -= 22

        if self.do:
            y -= 15
            c.setFont(brand.fonts["primary_bold"], 12)
            c.setFillColor(brand.color("navy"))
            c.drawString(30 * mm, y, self.do_heading)
            y -= 22
            for rule in self.do:
                c.setFillColor(brand.color("accent_green"))
                c.setFont(brand.fonts["primary_bold"], 14)
                c.drawString(30 * mm, y, "\u2713")
                c.setFont(brand.fonts["primary"], 10.5)
                c.setFillColor(brand.color("dark_text"))
                c.drawString(40 * mm, y, rule)
                y -= 22

        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Data Table
# ═══════════════════════════════════════════════════════════════════

@register("data_table")
class DataTable:
    """Tabular data page with header row and zebra striping."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "Data")
        self.subtitle = spec.get("subtitle", "")
        self.columns = spec.get("columns", [])
        self.rows = spec.get("rows", [])
        self.col_widths = spec.get("col_widths", [])
        # columns: ["Name", "Status", "Score"]
        # rows: [["Task A", "Done", "95%"], ...]

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)

        x_start = 30 * mm
        usable_w = W - 60 * mm
        n_cols = len(self.columns) if self.columns else 1
        if self.col_widths:
            widths = [w * mm for w in self.col_widths]
        else:
            widths = [usable_w / n_cols] * n_cols
        row_h = 20

        y = H - 75 * mm

        # Header row
        c.setFillColor(brand.color("navy"))
        c.rect(x_start, y - row_h, usable_w, row_h, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(brand.fonts["primary_bold"], 9)
        x = x_start
        for i, col in enumerate(self.columns):
            c.drawString(x + 4, y - row_h + 6, str(col))
            x += widths[i] if i < len(widths) else widths[-1]
        y -= row_h

        # Data rows
        for ri, row in enumerate(self.rows):
            if y < 30 * mm:
                c.showPage()
                draw_page_header(c, brand, W, H, self.heading + " (cont.)", page_num=page_num)
                draw_footer(c, brand, W, H)
                y = H - 75 * mm
                # Re-draw header
                c.setFillColor(brand.color("navy"))
                c.rect(x_start, y - row_h, usable_w, row_h, fill=1, stroke=0)
                c.setFillColor(white)
                c.setFont(brand.fonts["primary_bold"], 9)
                x = x_start
                for i, col in enumerate(self.columns):
                    c.drawString(x + 4, y - row_h + 6, str(col))
                    x += widths[i] if i < len(widths) else widths[-1]
                y -= row_h

            if ri % 2 == 0:
                c.setFillColor(brand.color("light_bg"))
                c.rect(x_start, y - row_h, usable_w, row_h, fill=1, stroke=0)
            c.setFillColor(brand.color("dark_text"))
            c.setFont(brand.fonts["primary"], 9)
            x = x_start
            for i, cell in enumerate(row):
                c.drawString(x + 4, y - row_h + 6, str(cell))
                x += widths[i] if i < len(widths) else widths[-1]
            y -= row_h

        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Metrics Card
# ═══════════════════════════════════════════════════════════════════

@register("metrics")
class MetricsPage:
    """KPI-style metric cards in a grid layout."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "Key Metrics")
        self.subtitle = spec.get("subtitle", "")
        self.cards = spec.get("cards", [])
        # cards: [{"label": "Tests Passed", "value": "142", "trend": "+12%"}]

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)

        if not self.cards:
            c.showPage()
            return

        cols = min(len(self.cards), 3)
        card_w = (W - 60 * mm - (cols - 1) * 8 * mm) / cols
        card_h = 50 * mm
        y = H - 80 * mm

        for i, card in enumerate(self.cards):
            col = i % cols
            row = i // cols
            cx = 30 * mm + col * (card_w + 8 * mm)
            cy = y - row * (card_h + 8 * mm)

            if cy - card_h < 30 * mm:
                c.showPage()
                draw_page_header(c, brand, W, H, self.heading + " (cont.)", page_num=page_num)
                draw_footer(c, brand, W, H)
                y = H - 80 * mm
                cy = y

            # Card background
            c.setFillColor(brand.color("light_bg"))
            c.roundRect(cx, cy - card_h, card_w, card_h, 8, fill=1, stroke=0)
            # Accent bar
            c.setFillColor(brand.color("teal"))
            c.rect(cx, cy - 4, card_w, 4, fill=1, stroke=0)
            # Value
            c.setFont(brand.fonts["primary_bold"], 28)
            c.setFillColor(brand.color("navy"))
            c.drawCentredString(cx + card_w / 2, cy - card_h / 2 + 2, str(card.get("value", "")))
            # Label
            c.setFont(brand.fonts["primary"], 9)
            c.setFillColor(brand.color("medium_gray"))
            c.drawCentredString(cx + card_w / 2, cy - card_h + 16, card.get("label", ""))
            # Trend
            trend = card.get("trend", "")
            if trend:
                is_positive = trend.startswith("+")
                c.setFont(brand.fonts["primary_bold"], 10)
                c.setFillColor(brand.color("accent_green") if is_positive else brand.color("accent_red"))
                c.drawCentredString(cx + card_w / 2, cy - card_h / 2 - 16, trend)

        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Bar Chart
# ═══════════════════════════════════════════════════════════════════

@register("bar_chart")
class BarChart:
    """Simple horizontal bar chart from data pairs."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "Chart")
        self.subtitle = spec.get("subtitle", "")
        self.bars = spec.get("bars", [])
        # bars: [{"label": "Sprint 1", "value": 85, "color": "#38A3A5"}]

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)

        if not self.bars:
            c.showPage()
            return

        max_val = max(b.get("value", 0) for b in self.bars) or 1
        bar_area_x = 70 * mm
        bar_area_w = W - bar_area_x - 30 * mm
        bar_h = 14 * mm
        gap = 6 * mm
        y = H - 80 * mm

        for bar in self.bars:
            val = bar.get("value", 0)
            label = bar.get("label", "")
            color = bar.get("color", "#38A3A5")
            w = (val / max_val) * bar_area_w

            # Label
            c.setFont(brand.fonts["primary"], 9)
            c.setFillColor(brand.color("dark_text"))
            c.drawRightString(bar_area_x - 4 * mm, y - bar_h / 2 - 3, label)
            # Background
            c.setFillColor(brand.color("light_bg"))
            c.roundRect(bar_area_x, y - bar_h, bar_area_w, bar_h, 4, fill=1, stroke=0)
            # Bar
            c.setFillColor(HexColor(color))
            if w > 8:
                c.roundRect(bar_area_x, y - bar_h, w, bar_h, 4, fill=1, stroke=0)
            # Value text
            c.setFont(brand.fonts["primary_bold"], 8)
            c.setFillColor(brand.color("navy"))
            c.drawString(bar_area_x + w + 3, y - bar_h / 2 - 3, str(val))

            y -= bar_h + gap

        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Pie Chart (simple donut)
# ═══════════════════════════════════════════════════════════════════

@register("pie_chart")
class PieChart:
    """Simple pie / donut chart with legend."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "Distribution")
        self.subtitle = spec.get("subtitle", "")
        self.slices = spec.get("slices", [])
        self.donut = spec.get("donut", True)
        # slices: [{"label": "...", "value": 40, "color": "#38A3A5"}, ...]

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)

        if not self.slices:
            c.showPage()
            return

        total = sum(s.get("value", 0) for s in self.slices) or 1
        cx_pt = W * 0.38
        cy_pt = H * 0.48
        radius = 70
        inner_r = radius * 0.55 if self.donut else 0

        angle = 90  # start from top
        for sl in self.slices:
            val = sl.get("value", 0)
            sweep = -(val / total) * 360
            color = sl.get("color", "#38A3A5")
            c.setFillColor(HexColor(color))
            # Draw wedge using path
            p = c.beginPath()
            p.moveTo(cx_pt, cy_pt)
            p.arc(cx_pt - radius, cy_pt - radius, cx_pt + radius, cy_pt + radius,
                  angle, sweep)
            p.close()
            c.drawPath(p, fill=1, stroke=0)
            angle += sweep

        # Donut hole
        if self.donut:
            c.setFillColor(white)
            c.circle(cx_pt, cy_pt, inner_r, fill=1, stroke=0)

        # Legend
        legend_x = W * 0.62
        legend_y = cy_pt + len(self.slices) * 10
        for sl in self.slices:
            c.setFillColor(HexColor(sl.get("color", "#38A3A5")))
            c.rect(legend_x, legend_y - 4, 10, 10, fill=1, stroke=0)
            c.setFont(brand.fonts["primary"], 9)
            c.setFillColor(brand.color("dark_text"))
            pct = (sl.get("value", 0) / total) * 100
            c.drawString(legend_x + 16, legend_y - 3, f"{sl.get('label', '')}  ({pct:.0f}%)")
            legend_y -= 18

        c.showPage()


# ═══════════════════════════════════════════════════════════════════
# Timeline / Roadmap
# ═══════════════════════════════════════════════════════════════════

@register("timeline")
class TimelinePage:
    """Vertical timeline / roadmap visualization."""

    def __init__(self, spec: dict):
        self.heading = spec.get("heading", "Timeline")
        self.subtitle = spec.get("subtitle", "")
        self.events = spec.get("events", [])
        # events: [{"date": "Q1 2026", "title": "...", "desc": "...", "status": "done|in-progress|planned"}]

    def render(self, c, brand, W, H, **kw):
        page_num = kw.get("page_num")
        draw_page_header(c, brand, W, H, self.heading, self.subtitle, page_num)
        draw_footer(c, brand, W, H)

        if not self.events:
            c.showPage()
            return

        line_x = 55 * mm
        y = H - 80 * mm
        dot_r = 5

        status_colors = {
            "done": brand.color("accent_green"),
            "in-progress": brand.color("teal"),
            "planned": brand.color("light_gray"),
        }

        for i, evt in enumerate(self.events):
            if y < 40 * mm:
                c.showPage()
                draw_page_header(c, brand, W, H, self.heading + " (cont.)", page_num=page_num)
                draw_footer(c, brand, W, H)
                y = H - 80 * mm

            status = evt.get("status", "planned")
            dot_color = status_colors.get(status, brand.color("medium_gray"))

            # Vertical line
            if i < len(self.events) - 1:
                c.setStrokeColor(brand.color("light_gray"))
                c.setLineWidth(2)
                c.line(line_x, y - dot_r, line_x, y - 50)

            # Dot
            c.setFillColor(dot_color)
            c.circle(line_x, y, dot_r, fill=1, stroke=0)

            # Date
            c.setFont(brand.fonts["primary_bold"], 9)
            c.setFillColor(brand.color("medium_gray"))
            c.drawRightString(line_x - 12, y - 3, evt.get("date", ""))

            # Title & desc
            c.setFont(brand.fonts["primary_bold"], 11)
            c.setFillColor(brand.color("navy"))
            c.drawString(line_x + 14, y - 3, evt.get("title", ""))
            desc = evt.get("desc", "")
            if desc:
                c.setFont(brand.fonts["primary"], 9)
                c.setFillColor(brand.color("medium_gray"))
                c.drawString(line_x + 14, y - 16, desc)

            y -= 50

        c.showPage()
