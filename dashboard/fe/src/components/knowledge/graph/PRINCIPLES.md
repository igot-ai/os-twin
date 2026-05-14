# Graph Component Principles

These 10 commitments govern every change to `src/components/knowledge/graph/`.
Every PR is reviewed against them. Violations are blockers.

---

## 1. No metaphor outranks the data

"Cosmic," "supernova," "ignition," "constellation" — gone.
Names refer to what they are: `graph`, `node`, `edge`, `selection`,
`highlight`, `path`, `focus`. Code should read like a specification,
not a marketing page.

## 2. Visual encoding is contractual

Shape, size, color, opacity, stroke each encode **exactly one** data
dimension. Documented in `palette-spec.md`. Reviewed in design QA
before merge. If a reviewer cannot answer "why is this a cube?" from
the spec alone, the encoding is wrong.

## 3. Determinism over delight

Same data + same camera = pixel-identical render. No `Math.random()`
(use seeded RNG). No time-driven effects except dashed-line stroke
offset, which is opt-out via `prefers-reduced-motion`.

## 4. Motion is signal, not decoration

Only state changes animate. Maximum animation duration **250ms**.
No idle motion. No camera orbit, parallax, or drift at rest.

## 5. Tokens are mandatory

Zero hex literals (`#rrggbb`) in component files under `graph/`.
All color values come from CSS custom properties via `theme.ts` or
from `constants.ts` which mirrors the token system.
Audited by ESLint rule `no-restricted-syntax` blocking
`#[0-9a-fA-F]{3,6}` regex inside `graph/**/*.tsx`.

## 6. Accessibility is a feature, not a phase

Every interactive element keyboard-reachable. Every state change
announced via `aria-live`. Tested with VoiceOver and NVDA.
`prefers-reduced-motion` and `prefers-contrast: more` honored
in every component.

## 7. Performance is a budget, not a goal

- **60fps** at 2k nodes on Intel Iris Xe
- **30fps** at 5k nodes on Intel Iris Xe
- Degradation strategy documented in `perf/lod-policy.ts`
- Frame budget regressions caught by Playwright perf tests

## 8. Print parity

Anything visible on screen exports to PDF/PNG with no loss of meaning.
PNG at 4096x4096, SVG for vector embedding, CSV for data export.

## 9. State is serializable

Camera, selection, filters, path all encode to a URL fragment.
`?view=<base64>` restores the exact view. Sharing a link reproduces
a colleague's view.

## 10. No new dependencies without justification

Each `package.json` line gets a one-line rationale in `DEPENDENCIES.md`.
No addition without a corresponding entry.
