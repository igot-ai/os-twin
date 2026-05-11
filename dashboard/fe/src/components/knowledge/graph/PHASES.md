# Graph Refactor — Phase Breakdown

Phase 1 (rename + docs) is **DONE**. Phases 2–10 are ready for pickup.
Each phase is independently mergeable. Acceptance criteria are
concrete — no phase is "done" until they pass.

---

## Phase 1 — Rename + restructure ✅ DONE

- `supernova/` → `graph/`
- Substructure created: `nodes/`, `edges/`, `labels/`, `camera/`,
  `interaction/`, `controls/`, `effects/`, `state/`, `theme/`,
  `a11y/`, `export/`, `perf/`
- Files moved into subfolders
- All imports updated
- `PRINCIPLES.md`, `palette-spec.md`, `DEPENDENCIES.md` written
- No behavior change

---

## Phase 2 — Type split + state extraction

**Owner:** ________
**Estimate:** 1 day

### Tasks

1. Split `SimNode` (in `simulation/types.ts`) into three types:
   - `SimNode` — physics-only: `{ id, x, y, z, vx, vy, vz, degree }`
   - `RenderNode` — view-only: `{ id, name, label, archetype, score, degree, geometryId, baseColor, emissiveColor, scaleClass }`
   - `PlacedNode extends RenderNode` — adds `{ x, y, z }` for the scene

2. Worker `postMessage` shrinks to positions-only `Float64Array`.
   Main thread joins by index against `RenderNode[]`.

3. Introduce `state/view-store.ts` (zustand):
   ```ts
   interface GraphViewState {
     selectedId: string | null;
     highlightedLabels: Set<string>;
     ignitionSet: Set<string>;
     pathSet: Set<string>;
     cameraState: CameraState;
     filterMode: 'all' | 'top-degree' | 'connected-only';
   }
   ```

4. `GraphScene` consumes store, drops prop drill.
   `SceneContent` takes ≤4 props.

### Acceptance

- [ ] Worker → main payload size drops by >60% (measured)
- [ ] `SceneContent` takes ≤4 props
- [ ] No regression in interaction (click, select, path)
- [ ] All existing tests pass

---

## Phase 3 — Token enforcement

**Owner:** ________
**Estimate:** 0.5 day

### Tasks

1. All hex literals in `edges/EdgeLines.tsx` (lines 6-7), `labels/NodeLabels.tsx`
   (lines 60-61, 124), `nodes/NodeInstances.tsx` (line 317), `GraphScene.tsx`
   (lines 73, 75-76) consolidated into `theme/theme.ts`

2. New `theme/theme.ts` reads `getComputedStyle(documentElement)` once on mount,
   exposes typed token map. Three.js materials consume from this map.

3. ESLint rule: `no-restricted-syntax` blocking `#[0-9a-fA-F]{3,6}`
   regex inside `graph/**/*.tsx`

### Current hex violations

| File | Line | Value | Replace with token |
|---|---|---|---|
| `edges/EdgeLines.tsx` | 6 | `#fbbf24` | `--graph-path-highlight` |
| `edges/EdgeLines.tsx` | 7 | `#2a2a3a` | `--graph-surface-light` |
| `GraphScene.tsx` | 73 | `#0a0a12` | `--graph-surface` |
| `GraphScene.tsx` | 75 | `#c8d0e0` | new token `--graph-light-primary` |
| `GraphScene.tsx` | 76 | `#8090b0` | new token `--graph-light-secondary` |
| `labels/NodeLabels.tsx` | 60 | `#c8d2e6` | `--graph-label-color` |
| `labels/NodeLabels.tsx` | 124 | `#000000` | `--graph-surface` |
| `nodes/NodeInstances.tsx` | 317 | `#ffffff` | `--graph-selection-ring` |

### Acceptance

- [ ] Lint passes (no hex literals in `graph/**/*.tsx`)
- [ ] Switching CSS root variable instantly retints the graph
- [ ] `[data-theme="high-contrast"]` visually verified

---

## Phase 4 — Shape language

**Owner:** ________
**Estimate:** 1 day

### Tasks

1. Refactor `nodes/archetypes.ts` to map archetype → geometry
   (not label → shape)

2. New `nodes/geometry-registry.ts` with 5 deliberate geometries:

   | Geometry | Archetype |
   |---|---|
   | `sphere-hi` (24-seg) | `hub` |
   | `octahedron` | `authority`, `authority-featured` |
   | `cube` | `structural` |
   | `cylinder` | `transient` |
   | `sphere-lo` (8-seg) | `peripheral`, `fragment` |

3. Add `ScaleClass` enum (`small | medium | large | xlarge`),
   banded log-scale on degree (see `palette-spec.md` §2)

4. Document each in `palette-spec.md` with rationale + screenshot

### Acceptance

- [ ] Each archetype's shape rationale is one sentence a non-engineer can defend
- [ ] Visual snapshot stable across runs (no random jitter — see Phase 9)
- [ ] `getShapeType()` removed from `constants.ts`

---

## Phase 5 — Edge upgrade

**Owner:** ________
**Estimate:** 1.5 days

### Tasks

1. Replace `LineBasicMaterial` with `Line2`/`LineMaterial`
   (`three/examples/jsm/lines`)

2. Three render passes: background / foreground / path

3. `edges/PathEdges.tsx` with dashed-line shader and `uTime` offset

4. `prefers-reduced-motion` freezes dash offset

5. Enable `frustumCulled` on edge geometry

### Acceptance

- [ ] Edge width visually identical on macOS Safari, Windows Edge, Linux Firefox
- [ ] Path edges distinguishable from foreground edges for colorblind users
- [ ] 4k edges render at 60fps on Iris Xe
- [ ] `frustumCulled={false}` removed from all edge components

---

## Phase 6 — Label overlay

**Owner:** ________
**Estimate:** 1 day

### Tasks

1. New `labels/LabelOverlay.tsx` (HTML `<div>` per visible label,
   absolutely positioned)

2. Project positions in `useFrame` via `labels/label-projection.ts`,
   write `style.transform` directly (no React re-render)

3. LOD policy in `labels/lod.ts`: visible if
   `degree > threshold(zoom)` OR selected OR in path

4. Remove drei `Text` dependency from labels

### Acceptance

- [ ] Vietnamese diacritics render correctly on Windows Chrome
- [ ] Labels are selectable, copyable, screen-reader visible
- [ ] 1000 labels visible without dropping below 50fps
- [ ] `@react-three/drei` `Text` import removed from `labels/`

---

## Phase 7 — Camera + interaction governance

**Owner:** ________
**Estimate:** 1 day

### Tasks

1. `camera/camera-config.ts` with documented constants
   (every magic number has a one-line rationale)

2. `camera/view-state.ts` serializes `{position, target, zoom}`
   to a URL fragment

3. `interaction/KeyboardNav.tsx`: Tab cycles nodes by degree desc,
   Shift+Tab reverse, Enter selects, F fits, R resets, Esc deselects

4. Focus tween clamped to 250ms; 0ms under `prefers-reduced-motion`

5. Remove the 800ms `setTimeout` in `CameraController.tsx:38`

### Current magic numbers to document

| File | Line | Value | What |
|---|---|---|---|
| `camera/CameraController.tsx` | 15 | `0.06` | FOCUS_LERP damping |
| `camera/CameraController.tsx` | 38 | `800` | ms delay before fit-to-view |
| `camera/CameraController.tsx` | 119 | `0.1` | OrbitControls dampingFactor |
| `camera/CameraController.tsx` | 120 | `8000` | maxDistance |
| `camera/CameraController.tsx` | 121 | `1.2` | zoomSpeed |
| `camera/CameraController.tsx` | 122 | `1.0` | panSpeed |

### Acceptance

- [ ] Full keyboard navigation from `Tab` only passes usability test
- [ ] `?view=<base64>` URL restores exact camera + selection
- [ ] 800ms setTimeout removed

---

## Phase 8 — Perf hardening

**Owner:** ________
**Estimate:** 1 day

### Tasks

1. Enable frustum culling: per-instance bounding spheres
   (compute on layout converge)

2. LOD: at low zoom, instance-cull peripheral/fragment nodes

3. `perf/perf-monitor.ts` exposes frame-time histogram on `window.__graphPerf`

4. `perf/perf-mode.ts`: auto-detect from DPR + heuristic

5. DPR cap: 1.0 on integrated GPU, 1.5 on dedicated, 2.0 opt-in only

### Acceptance

- [ ] 2k nodes / 5k edges → 60fps on M1, 30fps on Iris Xe
- [ ] 5k nodes / 10k edges → 30fps on M1, graceful degradation on Iris Xe
- [ ] `frustumCulled={false}` removed from `nodes/NodeInstances.tsx`

---

## Phase 9 — Determinism

**Owner:** ________
**Estimate:** 0.5 day

### Tasks

1. Seeded RNG for force-simulation jitter
   (`simulation/use-force-layout.ts:197` — `Math.random()`)

2. Seed derived from `nodes.map(n=>n.id).sort().join()` so same input
   set is reproducible

3. All "time" inputs to shaders gate behind motion preference

### Acceptance

- [ ] Layout snapshot test: same data + same window size → identical
  positions (within 1e-6)
- [ ] Pixel snapshot tests stable across CI runs
- [ ] `Math.random()` removed from `graph/` (lint rule)

---

## Phase 10 — Export + share + a11y audit

**Owner:** ________
**Estimate:** 1 day

### Tasks

1. `export/export-png.ts`: Canvas ref → `toDataURL` at 2x DPR
2. `export/export-svg.ts`: CPU-side simplified rendering
3. `export/export-csv.ts`: visible-nodes table
4. `export/share-url.ts`: query-string state encoding
5. axe-core run in CI; manual VoiceOver/NVDA pass logged in `a11y/AUDIT.md`

### Acceptance

- [ ] PNG export at 4096x4096 succeeds in <2s
- [ ] SVG export opens in Adobe Illustrator and Inkscape
- [ ] axe-core reports 0 violations
- [ ] VoiceOver announces: load summary, selection changes, filter changes

---

## Naming cleanup (cross-cutting)

Not a separate phase — address alongside the phase that touches each file:

| Current | Replacement | Phase |
|---|---|---|
| `ignitionSet` | `expandedSet` | Phase 2 (state) |
| `activeIgnitionPoints` | `activeExpansionPoints` | Phase 2 (state) |
| `isIgnited` | `isExpanded` | Phase 4 (nodes) |
| `connectsIgnited` | `connectsExpanded` | Phase 5 (edges) |
| `ignite()` (hook) | `expand()` | Phase 2 (state) |
| `ignited` (UI text) | `expanded` | Phase 7 (interaction) |

---

## y-flip normalization (cross-cutting)

`y = -node.y` is scattered across 5 files. Normalize once in a
shared utility function, consumed everywhere:

```ts
// simulation/coord-transform.ts
export function toSceneY(simY: number): number {
  return -simY;
}
```

| File | Lines | Phase |
|---|---|---|
| `nodes/NodeInstances.tsx` | 247 | Phase 4 |
| `edges/EdgeLines.tsx` | 93, 95, 127, 128 | Phase 5 |
| `labels/NodeLabels.tsx` | 55, 89, 92 | Phase 6 |
| `camera/CameraController.tsx` | 73 | Phase 7 |

---

## Sprint recommendation

**Sprint 1 (5 days):** Phases 1 (done), 3, 4, 5, 7
**Sprint 2 (4 days):** Phases 2, 6, 8, 9, 10
