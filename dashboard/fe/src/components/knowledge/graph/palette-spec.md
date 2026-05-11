# Graph Palette Specification

This document is the contractual source of truth for every visual
encoding in the knowledge graph. If a visual property is not listed
here with a rationale, it must not appear in the render.

---

## 1. Shape Language

Each node archetype maps to exactly one geometry. The mapping is
deterministic: same archetype always produces the same shape.

| Geometry | Archetype | Entity Labels | Visual Rationale |
|---|---|---|---|
| `sphere-hi` (24 segments) | `hub` | Top-5% degree nodes (computed) | Mass without facets = "central, established, well-known" |
| `octahedron` | `authority`, `authority-featured` | Person, Organization, Entity, Event, Group | Faceted regular solid = "structured actor with agency" |
| `cube` | `structural` | Concept, Technology, Law | Right angles = "rigid system / rule / principle" |
| `cylinder` | `transient` | Document, Media | Time-bound artifact = "record / file" |
| `sphere-lo` (8 segments) | `peripheral`, `fragment` | Location, Date, Money, City, Country, Chunk | Smallest, simplest = "attribute / supporting evidence" |

**Previous state (deleted):** 6 shapes (cube, dodecahedron, icosahedron,
tetrahedron, octahedron, sphere) mapped to labels with no semantic
story. A government analyst could not answer "why is this a cube?"

---

## 2. Size Encoding

Size encodes **degree** (connection count), banded into 4 discrete
scale classes. No continuous scaling — ensures reproducibility and
predictable visual density.

| ScaleClass | Degree Range | Scale Multiplier | Rationale |
|---|---|---|---|
| `small` | degree 0–1 | 0.6 | Leaf/fragment — minimal visual mass |
| `medium` | degree 2–5 | 1.0 | Default — most nodes |
| `large` | degree 6–20 | 1.6 | Connected — above-average connectivity |
| `xlarge` | degree 21+ | 2.4 | Hub — top-tier connector |

Degree thresholds are log-banded. The formula:

```
scaleClass = degree === 0   ? 'small'
           : degree <= 5    ? 'medium'
           : degree <= 20   ? 'large'
           :                  'xlarge'
```

**Hub archetype overrides:** If a node qualifies as `hub` (top 5%
degree), it uses `sphere-hi` geometry *and* `xlarge` scale regardless
of the archetype-to-scale mapping above.

---

## 3. Color Encoding

Color encodes **entity label** (type). The CSS custom properties in
`graph-tokens.css` are the source of truth; `constants.ts` mirrors
them for Three.js materials that cannot read CSS variables at runtime.

### 3.1 Node Colors — Default Theme

| Token | Label | Hex | WCAG Contrast (on `#0a0a12`) |
|---|---|---|---|
| `--graph-node-entity` | Entity | `#3b82f6` | 4.2:1 AA |
| `--graph-node-person` | Person | `#a78bfa` | 5.8:1 AA |
| `--graph-node-organization` | Organization | `#f472b6` | 4.6:1 AA |
| `--graph-node-location` | Location | `#fb923c` | 5.1:1 AA |
| `--graph-node-event` | Event | `#34d399` | 7.2:1 AAA |
| `--graph-node-concept` | Concept | `#22d3ee` | 7.8:1 AAA |
| `--graph-node-document` | Document | `#818cf8` | 4.1:1 AA |
| `--graph-node-date` | Date | `#facc15` | 8.4:1 AAA |
| `--graph-node-product` | Product | `#2dd4bf` | 6.9:1 AAA |
| `--graph-node-technology` | Technology | `#c084fc` | 5.3:1 AA |
| `--graph-node-country` | Country | `#fb7185` | 4.4:1 AA |
| `--graph-node-city` | City | `#38bdf8` | 5.6:1 AA |
| `--graph-node-money` | Money | `#a3e635` | 7.1:1 AAA |
| `--graph-node-law` | Law | `#e879f9` | 4.8:1 AA |
| `--graph-node-media` | Media | `#fdba74` | 5.9:1 AA |
| `--graph-node-group` | Group | `#22d3ee` | 7.8:1 AAA |
| `--graph-node-text_chunk` | Chunk | `#475569` | 2.8:1 (muted by design) |

**Note:** `text_chunk` is intentionally low-contrast — fragments are
background noise. In `prefers-contrast: more` mode, the token is
boosted to `#6080a0` (4.1:1 AA).

### 3.2 Edge Colors

| Token | Relationship | Hex |
|---|---|---|
| `--graph-edge-mentions` | MENTIONS | `#60a5fa` |
| `--graph-edge-knows` | KNOWS | `#a78bfa` |
| `--graph-edge-related_to` | RELATED_TO | `#34d399` |
| `--graph-edge-references` | REFERENCES | `#fbbf24` |
| `--graph-edge-uses` | USES | `#f472b6` |
| `--graph-edge-contains` | CONTAINS | `#fb923c` |
| `--graph-edge-relates` | RELATES | `#6b7280` |

---

## 4. Edge Rendering

Three layers, three passes, one material per layer:

| Layer | Material | Width (world units) | Opacity | When |
|---|---|---|---|---|
| Background | `Line2` / `LineMaterial` | 1.0 | 0.25 | All edges, always |
| Foreground | `Line2` / `LineMaterial` | 1.5 | 0.85 | Edges incident to selected or highlighted-label nodes |
| Path | `Line2` + dashed shader | 2.5 | 1.0 | Edges in `selectedPath`. Animated dash offset; disabled under `prefers-reduced-motion` |

**No curves by default.** Straight lines export cleanly and read
predictably under rotation. Curves are behind a user-opt-in flag only.

**Previous state (deleted):** `LineBasicMaterial` with `linewidth: 1`,
silently ignored on Windows/Linux WebGL. Edges looked inconsistent
across platforms.

---

## 5. Selection Ring

| Property | Value | Token |
|---|---|---|
| Color | `#ffffff` / high-contrast `#ffffff` | `--graph-selection-ring` |
| Opacity | 0.8 | — |
| Width | 15% larger than node scale | — |
| Depth test | Disabled | — |
| Side | `DoubleSide` | — |

**Previous state (deleted):** Plain `opacity: 0.6` white ring, not in
token system, failed WCAG contrast in some color combos.

---

## 6. Label Rendering

Labels are HTML `<div>` elements projected from 3D coordinates — not
drei `Text` meshes. See `labels/LabelOverlay.tsx`.

| Property | Value |
|---|---|
| Font | System UI (inherits from page) |
| Size | 11px default, 14px selected |
| Truncation | 32 chars, full text in `title=` |
| Selectable | Yes (copyable to clipboard) |
| Screen-reader | Visible in `aria-live` polite region |
| LOD | Visible if `degree > threshold(zoom)` OR selected OR in path |

**Previous state (deleted):** drei `<Text>` per node — not selectable,
not screen-readable, fragile on Vietnamese diacritics, no RTL support.

---

## 7. High-Contrast Mode (`prefers-contrast: more`)

All tokens are overridden in `graph-tokens.css`. Key changes:

- Surface: `#0a0a12` → `#000000` (pure black)
- All node colors boosted by ~10-15% lightness
- Edge default: `#6b7280` → `#909090`
- Path highlight: `#fbbf24` → `#ffdd00`
- Fragment nodes (`text_chunk`): `#475569` → `#6080a0`

---

## 8. Prohibited Visual Elements

These are explicitly banned per PRINCIPLES.md §1 and §4:

- Bloom, glow halos, additive sprites
- Idle camera orbit / parallax / drift
- Particle dust, starfields, nebulas
- Random twinkles, pulses, or shimmers
- Curved edges by default
- Chromatic aberration, depth-of-field, vignette
- Per-node icons or images in 3D
- Skybox or 3D background imagery
- Camera shake on any event
