# Nexus Explorer Refactor Plan

Verified against code as of 2026-05-11. Every issue references actual file:line.

---

## 0. Verified Issues (what's actually wrong)

### Spatial / Layout

| # | Problem | Evidence | Severity |
|---|---------|----------|----------|
| L1 | **SearchBar floats at center top** overlapping the gradient toolbar below it. Both compete for visual attention at `top-3` and `top-0` respectively. | `SearchBar.tsx:28` — `absolute top-3 left-1/2 -translate-x-1/2` <br> `NexusHUD.tsx:112` — top bar at `top-0` with gradient | High |
| L2 | **Node legend (GraphScene) + ExplorationTrail (NexusHUD) stack in bottom-left corner.** Both are `absolute bottom-* left-*` — the legend is at `bottom-2 left-2` and the trail is at `bottom-16 left-3`. They collide and visually merge. | `GraphScene.tsx:386` — `absolute bottom-2 left-2` <br> `ExplorationTrail.tsx:50` — `absolute bottom-16 left-3` | Medium |
| L3 | **ContextualCard + Minimap share right side** — Card at `top-14 right-3`, Minimap at `bottom-14 right-3`. Currently Minimap is conditionally hidden (`!selectedNode`) to avoid collision, which is a fragile guard. | `ContextualCard.tsx:59` — `top-14 right-3` <br> `Minimap.tsx:97` — `bottom-14 right-3` <br> `NexusHUD.tsx:173` — `{!selectedNode && ... <Minimap>}` | Medium |
| L4 | **Every HUD element is `absolute` positioned** — no layout system, no reserved space, all floating. Makes adding new panels risky. | `NexusHUD.tsx:109` — `absolute inset-0 z-10 pointer-events-none` wrapper; every child is `absolute` | High |
| L5 | **ActionBar at bottom-center has no spatial relationship** to the legend or trail. It sits at `bottom-3 left-1/2 -translate-x-1/2` with `max-w-[420px]`. | `ActionBar.tsx:55` | Low |

### Redundancy / Confusion

| # | Problem | Evidence | Severity |
|---|---------|----------|----------|
| R1 | **Namespace shown in two places when nexus is inactive** — KnowledgeTabCore shows a `{selectedNamespace}` pill, and NamespaceSwitcher also shows it. The `!== 'nexus'` guard prevents double-show in nexus view, but when switching away from nexus, both appear momentarily. | `KnowledgeTabCore.tsx:306-310` — pill (guarded by `activeDetailView !== 'nexus'`) <br> `NamespaceSwitcher.tsx:18-31` — dropdown | Low |
| R2 | **"Expand" action exists in both ActionBar and ContextualCard.** Two buttons that call `onExpand(selectedNode.id)` — one in the floating bottom bar, one in the card footer. | `ActionBar.tsx:88-98` — Expand button <br> `ContextualCard.tsx:168-176` — Expand button | Medium |
| R3 | **Stats shown in ActionBar AND in GraphScene.** ActionBar shows `N nodes · M edges · K ignited` at bottom-center; GraphScene shows `K ignited` badge at top-right and `N nodes` in minimap footer. | `ActionBar.tsx:128-137` <br> `GraphScene.tsx:449-461` <br> `Minimap.tsx:108-112` | Low |

### Code Quality

| # | Problem | Evidence | Severity |
|---|---------|----------|----------|
| C1 | **NexusHUD has 24 props** — God-component anti-pattern. Every child's data and handlers are drilled through it. | `NexusHUD.tsx:17-48` — 24 props in interface | High |
| C2 | **Auto-seed useEffect suppresses exhaustive-deps** — `selectedNamespace` is the only dep but `nexus.isSeeded` and `nexus.seed` are used inside. This can fire spurious re-seeds. | `NexusExplorer.tsx:63-67` — `eslint-disable-line react-hooks/exhaustive-deps` | High |
| C3 | **`queryMode` is local state in NexusExplorer but should live in `useNexusExplorer`.** The hook owns all other exploration state; `queryMode` is the outlier. | `NexusExplorer.tsx:60` — `const [queryMode, setQueryMode] = useState<QueryMode>('graph')` <br> `use-nexus-explorer.ts` — no `queryMode` state | Medium |
| C4 | **EmptyState auto-picks `namespaces[0]`** — clicking "Select Namespace" picks the first namespace without user intent. | `NexusExplorer.tsx:100` — `namespaces[0].name` | High |
| C5 | **No keyboard shortcuts** — no `/` for search, `Esc` for deselect, `r` for reset, `1/2/3` for lens. | No `useEffect` with `keydown` listener anywhere in nexus/ | Medium |
| C6 | **No focus management** — opening ContextualCard doesn't trap focus; closing doesn't return it to canvas. | `ContextualCard.tsx` — no `useRef` focus or `aria-modal` | Low |
| C7 | **Typography scale sprawl** — 8 distinct sizes used: 8, 9, 10, 11, 12, 13, 14, 16px across the nexus components. No shared scale constant. | grep shows `text-[8px]`, `text-[9px]`, `text-[10px]`, `text-[11px]`, `text-[12px]`, `text-[13px]`, `text-[14px]`, `text-[16px]` all in use | Low |
| C8 | **Icon sizing inconsistent** — `material-symbols-outlined` icons use both Tailwind classes (`text-[12px]`) and inline styles (`style={{ fontSize: 10 }}`) interchangeably. | `ExplorationTrail.tsx:73` — `style={{ fontSize: 10 }}` <br> `LensSelector.tsx:31` — `text-[12px]` class | Low |

### UX Gaps

| # | Problem | Evidence | Severity |
|---|---------|----------|----------|
| U1 | **ContextualCard properties panel is 160px max-height** — for nodes with 15+ properties, this requires scrolling inside a tiny scrollport. | `ContextualCard.tsx:134` — `max-h-[160px] overflow-y-auto` | Medium |
| U2 | **`text_chunk` content (the most common node type) is buried inside the generic properties list** — no special rendering for the actual text content. | `ContextualCard.tsx:135-155` — all properties rendered identically in key/value list | Medium |
| U3 | **Depth indicator `d{N}` is discoverable only by hover tooltip** — no visible control to change it, no explanation of what it means without hovering. | `ActionBar.tsx:96` — `<span className="text-[9px] opacity-60" title={...}>d{expansionDepth}</span>` | Medium |
| U4 | **No loading skeleton** — while the graph loads, only a spinning border is shown (`GraphScene.tsx:301-307`). No skeleton for the HUD docks. | `GraphScene.tsx:298-325` — spinner + text only | Low |
| U5 | **Query error is a fixed-position red bar** at `top-20 left-1/2` — doesn't auto-dismiss, can overlap with search bar. | `NexusHUD.tsx:138-146` — error toast at `absolute top-20 left-1/2` | Low |

---

## 1. Phased Execution Plan

### Phase S1 — Context + Shell (foundation, no visual change)

**Goal:** Introduce `NexusContext` and `NexusShell` so later phases can move components without prop-drilling.

#### 1a. Create `NexusContext`

New file: `src/components/knowledge/nexus/NexusContext.tsx`

```
NexusContext provides:
  - namespace state (namespace, onNamespaceChange)
  - graph state (nodes, edges, selectedNode, activeLens, expansionDepth, etc.)
  - query state (queryResult, queryLoading, queryError, queryMode)
  - trail state
  - all action handlers (seed, expand, query, selectNode, etc.)
  - derived helpers (isLoading, isSeeded)
```

Source: All values currently passed as NexusHUD's 24 props. The context reads from `useNexusExplorer` and `NexusExplorer` local state.

#### 1b. Create `NexusShell` grid layout

New file: `src/components/knowledge/nexus/NexusShell.tsx`

```
CSS Grid: 3 rows × 3 cols
  ┌──────────────────────────────────────────────────┐
  │  TOP RAIL (44px) — spans all 3 cols              │
  ├──────────┬────────────────────────┬──────────────┤
  │ LEFT     │                        │  RIGHT       │
  │ DOCK     │    CANVAS              │  DOCK        │
  │ (320px)  │    (flex-1)            │  (360px)     │
  │          │                        │              │
  ├──────────┴────────────────────────┴──────────────┤
  │  BOTTOM RAIL (36px) — spans all 3 cols           │
  └──────────────────────────────────────────────────┘
```

- Canvas slot: `<NexusCanvas>` (existing)
- Top rail slot: initially just `<NamespaceSwitcher>` + `<LensSelector>` + `<SearchBar>` (moved from floating to inline)
- Left dock slot: initially just `<ResultsDrawer>` + `<ExplorationTrail>` (moved from floating)
- Right dock slot: initially just `<ContextualCard>` (moved from floating)
- Bottom rail slot: initially just `<ActionBar>` (moved from floating)
- `FloatingMinimap` stays absolute but now lives in the canvas cell, not overlapping with docks

#### 1c. Refactor NexusExplorer to use Context + Shell

- `NexusExplorer.tsx` creates `NexusContext.Provider`, renders `<NexusShell>`
- `NexusHUD.tsx` becomes a thin orchestrator or is deleted — children read from context instead of props

**Files touched:**
- New: `nexus/NexusContext.tsx`, `nexus/NexusShell.tsx`
- Refactor: `NexusExplorer.tsx`, `NexusHUD.tsx` (delete or gut)
- No visual change — components render in their grid slots exactly as before

---

### Phase S2 — Top rail consolidation

**Goal:** Merge gradient toolbar, floating SearchBar, NamespaceSwitcher, and LensSelector into a single 44px rail.

#### 2a. Top rail component

New file: `src/components/knowledge/nexus/TopRail.tsx`

Layout:
```
[hub icon] [Namespace ▾]  │  🔍 [Explore knowledge…    ] [▾]  │  [Structural▾] [⌨︎] [⋯]
```

- Namespace: `NamespaceSwitcher` with friendlier labels (show short name, full hash on hover)
- Search: `SearchBar` content moved inline (no longer floating). The expand/collapse mode panel drops down from the rail.
- Lens: `LensSelector` stays as-is (already in top bar)
- `⌨︎`: opens keyboard shortcut popover (Phase S5)
- `⋯`: overflow menu (Reset, Export)

#### 2b. Remove the duplicate namespace pill

In `KnowledgeTabCore.tsx:306-310`, the namespace pill is already hidden during nexus view. No change needed — but add a comment clarifying this is intentional.

#### 2c. Remove top gradient bar

The `NexusHUD.tsx:111-123` gradient bar is replaced by the solid TopRail background. No more competing visual layers at top.

**Files touched:**
- New: `nexus/TopRail.tsx`
- Refactor: `nexus/SearchBar.tsx` (remove `absolute top-3 left-1/2` positioning)
- Refactor: `nexus/NamespaceSwitcher.tsx` (minor style adjustments for rail context)
- Refactor: `NexusHUD.tsx` (remove top bar section, lines 111-123)

---

### Phase S3 — Right dock: ContextualCard improvements

**Goal:** Fix the cramped properties panel and surface `text_chunk` content.

#### 3a. Increase properties panel height

`ContextualCard.tsx:134`: Change `max-h-[160px]` → `max-h-[320px]`. The card is already `w-[360px]` and lives in a dock with full height, so it can afford taller content.

#### 3b. Special-case `text_chunk` content

When `node.label === 'text_chunk'` and `node.properties.text` exists, render it as a readable paragraph above the properties list, not as a generic key/value row. Truncate to 500 chars with "Show more".

#### 3c. Remove duplicate Expand button from ActionBar

The Expand and Path buttons exist in both `ActionBar.tsx:88-113` and `ContextualCard.tsx:164-184`. Remove them from ActionBar since they only make sense when a node is selected (and the card is visible then). Keep them in ContextualCard's footer.

#### 3d. Move depth control inline with Expand

In `ContextualCard.tsx`, add a small depth selector next to the Expand button: `Expand ▾ d[1][2][3]`. This replaces the current `d{N}` indicator in ActionBar.

#### 3e. Add prologue/backlinks section

Below the name, show "found from: seed(50)" or "expanded from a78cc49b" — read from `trail` via context, find the last entry that resulted in this node appearing.

**Files touched:**
- Refactor: `nexus/ContextualCard.tsx` (major rewrite of body section)
- Refactor: `nexus/ActionBar.tsx` (remove Expand/Path buttons, remove `d{N}` indicator)

---

### Phase S4 — Bottom rail + legend consolidation

**Goal:** Move the node/edge legend from GraphScene into the bottom rail; eliminate spatial conflicts.

#### 4a. Create BottomRail component

New file: `src/components/knowledge/nexus/BottomRail.tsx`

Layout:
```
[Node legend: 🟦 text_chunk·47  🟣 entity·23  …]  │  324 nodes · 427 edges · 51 ignited
```

- Left side: node type filters (moved from `GraphScene.tsx:384-430`)
- Right side: stats (moved from `ActionBar.tsx:128-137`)
- `highlightedLabels` state currently lives in `GraphScene` — lift it to `NexusContext` so BottomRail can control it

#### 4b. Remove legend overlays from GraphScene

Delete the node legend (`GraphScene.tsx:384-430`), edge legend (`GraphScene.tsx:432-446`), and ignition badge (`GraphScene.tsx:449-461`). These move to BottomRail.

#### 4c. ActionBar becomes slim action strip

After S3 removed Expand/Path from ActionBar, it now only has: Sonar Ping / Reset / Clear Path. Move these into the BottomRail or TopRail `⋯` menu. Delete `ActionBar.tsx`.

**Files touched:**
- New: `nexus/BottomRail.tsx`
- Refactor: `GraphScene.tsx` (remove legend/badge overlays, lift `highlightedLabels` to context)
- Delete: `nexus/ActionBar.tsx`
- Refactor: `NexusContext.tsx` (add `highlightedLabels` state)

---

### Phase S5 — Left dock: Journey + Results

**Goal:** Combine ExplorationTrail and ResultsDrawer into a cohesive left panel.

#### 5a. Create LeftDock component

New file: `src/components/knowledge/nexus/LeftDock.tsx`

Two sections:
1. **Journey** (top) — vertical timeline of `ExplorationTrail` entries, newest on top. Clicking an entry scrolls to that state (future: graph state snapshots). Group consecutive expands.
2. **Results** (bottom) — existing `ResultsDrawer` content, no longer floating.

#### 5b. Collapsible dock

Each dock (left, right) has a collapse toggle. Persist collapse state to `localStorage` under key `nexus-dock-{left|right}`.

**Files touched:**
- New: `nexus/LeftDock.tsx`
- Refactor: `nexus/ExplorationTrail.tsx` (vertical layout instead of horizontal chips)
- Refactor: `nexus/ResultsDrawer.tsx` (remove `absolute top-14 left-3` positioning)
- New: `nexus/RightDock.tsx` (thin wrapper around ContextualCard)
- New: `nexus/useDockState.ts` (localStorage persistence)

---

### Phase S6 — Keyboard shortcuts + empty states

#### 6a. Keyboard shortcuts

New file: `src/components/knowledge/nexus/useShortcuts.ts`

```
/       → focus search input
Esc     → clear selection (or close right dock)
r       → reset graph
1/2/3   → set lens (structural/semantic/category)
[ / ]   → collapse left/right dock
?       → open shortcut cheatsheet popover
```

Register via `useEffect` + `document.addEventListener('keydown')` in `NexusShell`.

#### 6b. Fix EmptyState namespace auto-pick

`NexusExplorer.tsx:100`: Replace `namespaces[0].name` with a grid of namespace cards (name + size + last-updated). The "Select Namespace" button becomes a namespace picker, not a blind pick.

**Files touched:**
- New: `nexus/useShortcuts.ts`
- Refactor: `nexus/EmptyState.tsx` (namespace grid instead of single button)
- Refactor: `NexusExplorer.tsx:96-103` (remove auto-pick)

---

### Phase S7 — Code quality fixes

#### 7a. Fix auto-seed deps warning

`NexusExplorer.tsx:63-67`: Move auto-seed logic into `useNexusExplorer` hook itself. The hook already knows `namespace` and `isSeeded` — add an `autoSeed` option:

```ts
useNexusExplorer(namespace, { autoSeed: true, autoSeedTopK: 50 })
```

This removes the `eslint-disable` and the fragile deps array.

#### 7b. Move `queryMode` into `useNexusExplorer`

`NexusExplorer.tsx:60`: Delete local `queryMode` state. Add `queryMode` + `setQueryMode` to the hook's return. All consumers read from context.

#### 7c. Typography scale constant

New file: `src/components/knowledge/nexus/typography.ts`

```ts
export const FONT = {
  caption: 'text-[9px]',    // badges, counts
  label:   'text-[10px]',   // secondary labels
  body:    'text-[11px]',   // main UI text
  strong:  'text-[12px]',   // emphasized text
  heading: 'text-[14px]',   // card titles
} as const;
```

Replace all `text-[8px]` → `caption`, `text-[13px]` and `text-[16px]` → use the closest from the scale. Eliminate `text-[8px]` and `text-[13px]` usage entirely (8px → 9px, 13px → 12px or 14px).

#### 7d. Icon component

New file: `src/components/knowledge/nexus/Icon.tsx`

```tsx
export function Icon({ name, size = 14 }: { name: string; size?: number }) {
  return <span className="material-symbols-outlined" style={{ fontSize: size }}>{name}</span>;
}
```

Replace all `<span className="material-symbols-outlined" style={{ fontSize: N }}>` and `<span className="material-symbols-outlined text-[Npx]">` with `<Icon name="..." size={N} />`.

**Files touched:**
- Refactor: `NexusExplorer.tsx` (7a, 7b)
- Refactor: `use-nexus-explorer.ts` (7b — add queryMode state)
- New: `nexus/typography.ts`, `nexus/Icon.tsx`
- Refactor: all nexus/*.tsx (7c, 7d — adopt typography + Icon)

---

### Phase S8 — Polish (optional, lower priority)

#### 8a. Loading skeleton

Replace `GraphScene.tsx:298-325` spinner with skeleton: shimmer overlay on canvas area + skeleton cards in left/right docks.

#### 8b. Query error toast

`NexusHUD.tsx:138-146`: Move error display to bottom-rail toast slot, auto-dismiss after 6s, add retry button.

#### 8c. Focus management for ContextualCard

When card opens, focus the card container. When card closes, return focus to canvas. Add `aria-modal` and `role="dialog"`.

#### 8d. Force-simulation pause optimization

`useForceSimulation.ts`: When `alphaRef.current <= alphaMin`, the sim stops. Currently it only restarts via `reheat()`. Add a `pause()` / `resume()` API so the shell can pause the sim when no interaction is happening (e.g., both docks collapsed and no drag).

**Files touched:**
- Refactor: `GraphScene.tsx` (8a)
- Refactor: `nexus/NexusHUD.tsx` or `BottomRail.tsx` (8b)
- Refactor: `nexus/ContextualCard.tsx` (8c)
- Refactor: `supernova/useForceSimulation.ts` (8d)

---

## 2. Sprint Schedule

| Sprint | Scope | New Files | Modified Files | Deleted Files |
|--------|-------|-----------|----------------|---------------|
| **S1** | Phase S1: NexusContext + NexusShell | `NexusContext.tsx`, `NexusShell.tsx` | `NexusExplorer.tsx`, `NexusHUD.tsx` | — |
| **S2** | Phase S2: Top rail | `TopRail.tsx` | `SearchBar.tsx`, `NamespaceSwitcher.tsx`, `NexusHUD.tsx` | — |
| **S3** | Phase S3: Right dock / ContextualCard | — | `ContextualCard.tsx`, `ActionBar.tsx` | — |
| **S4** | Phase S4: Bottom rail + legend | `BottomRail.tsx` | `GraphScene.tsx`, `NexusContext.tsx` | `ActionBar.tsx` |
| **S5** | Phase S5: Left dock | `LeftDock.tsx`, `RightDock.tsx`, `useDockState.ts` | `ExplorationTrail.tsx`, `ResultsDrawer.tsx` | — |
| **S6** | Phase S6: Shortcuts + empty state | `useShortcuts.ts` | `EmptyState.tsx`, `NexusExplorer.tsx` | — |
| **S7** | Phase S7: Code quality | `typography.ts`, `Icon.tsx` | `NexusExplorer.tsx`, `use-nexus-explorer.ts`, all `nexus/*.tsx` | — |
| **S8** | Phase S8: Polish (opt-in) | — | `GraphScene.tsx`, `ContextualCard.tsx`, `useForceSimulation.ts` | — |

---

## 3. Quick Wins (standalone, do first if needed)

Each takes ~30–60 min and is visually obvious:

1. **Increase ContextualCard properties height**: `ContextualCard.tsx:134` — `max-h-[160px]` → `max-h-[320px]`
2. **Fix EmptyState auto-pick**: `NexusExplorer.tsx:100` — replace `namespaces[0].name` with namespace grid
3. **Remove duplicate Expand/Path from ActionBar**: `ActionBar.tsx:88-124` — delete these buttons (they exist in ContextualCard)
4. **Fix auto-seed deps warning**: Move auto-seed into `useNexusExplorer` hook
5. **Add keyboard `/` shortcut for search**: Add `useEffect` in `NexusExplorer.tsx` that focuses search on `/`
