# Graph Component Dependencies

Every dependency used by the graph component must have a one-line
rationale here. No additions without a corresponding entry.

| Package | Version | Rationale |
|---|---|---|
| `three` | ^0.184.0 | WebGL rendering engine — core of the 3D graph canvas |
| `@react-three/fiber` | ^9.6.1 | React reconciler for Three.js — declarative scene graph |
| `@react-three/drei` | ^10.7.7 | OrbitControls, Text (deprecated — replacing with HTML overlay) |
| `@react-three/postprocessing` | ^3.0.4 | EffectComposer for SMAA antialiasing pass |
| `postprocessing` | ^6.39.1 | Underlying postprocessing library used by the R3F wrapper |
| `@types/three` | ^0.184.1 | TypeScript type definitions for Three.js |
| `zustand` | ^5.0.12 | View state store — replacing prop drill in Phase 2 |
| `react-force-graph-2d` | ^1.29.1 | 2D fallback graph view (used in GraphView.tsx, not in 3D canvas) |

## Candidates for removal

- `@react-three/drei`: Only `OrbitControls` and `Text` remain in use.
  `Text` is being replaced by HTML overlay in Phase 6. After that,
  only `OrbitControls` depends on drei — evaluate inlining or
  importing from `three-stdlib` directly.

## Pending additions (Phase 2+)

- None yet. Each addition will be documented here at time of install.
