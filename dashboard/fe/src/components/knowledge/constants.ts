/**
 * Shared constants for Knowledge UI components.
 *
 * Color values here MUST match graph-tokens.css --graph-node-* tokens.
 * The CSS tokens are the source of truth for HTML/overlay rendering;
 * these JS constants are used by Three.js materials that cannot read CSS vars.
 */

export interface LabelColorPair {
  base: string;
  emissive: string;
}

export const LABEL_COLORS: Record<string, LabelColorPair> = {
  text_chunk:   { base: '#475569', emissive: '#64748b' },
  person:       { base: '#a78bfa', emissive: '#c4b5fd' },
  organization: { base: '#f472b6', emissive: '#fbcfe8' },
  location:     { base: '#fb923c', emissive: '#fdba74' },
  event:        { base: '#34d399', emissive: '#6ee7b7' },
  concept:      { base: '#22d3ee', emissive: '#67e8f9' },
  document:     { base: '#818cf8', emissive: '#a5b4fc' },
  date:         { base: '#facc15', emissive: '#fde047' },
  product:      { base: '#2dd4bf', emissive: '#5eead4' },
  technology:   { base: '#c084fc', emissive: '#d8b4fe' },
  country:      { base: '#fb7185', emissive: '#fda4af' },
  city:         { base: '#38bdf8', emissive: '#7dd3fc' },
  money:        { base: '#a3e635', emissive: '#bef264' },
  law:          { base: '#e879f9', emissive: '#f0abfc' },
  media:        { base: '#fdba74', emissive: '#fed7aa' },
  group:        { base: '#22d3ee', emissive: '#67e8f9' },
  entity:       { base: '#3b82f6', emissive: '#60a5fa' },
};

export const EDGE_LABEL_COLORS: Record<string, string> = {
  MENTIONS: '#60a5fa',
  KNOWS: '#a78bfa',
  RELATED_TO: '#34d399',
  REFERENCES: '#fbbf24',
  USES: '#f472b6',
  CONTAINS: '#fb923c',
  RELATES: '#6b7280',
};

export type NodeShapeType = 'sphere' | 'octahedron' | 'box' | 'tetrahedron' | 'dodecahedron' | 'icosahedron';

export const SHAPE_TYPES: NodeShapeType[] = ['sphere', 'octahedron', 'box', 'tetrahedron', 'dodecahedron', 'icosahedron'];

export const LABEL_SHAPES: Record<string, NodeShapeType> = {
  entity: 'icosahedron',
  person: 'octahedron',
  organization: 'box',
  location: 'tetrahedron',
  event: 'dodecahedron',
  concept: 'icosahedron',
  document: 'box',
  date: 'tetrahedron',
  product: 'dodecahedron',
  technology: 'octahedron',
  country: 'octahedron',
  city: 'tetrahedron',
  money: 'dodecahedron',
  law: 'box',
  media: 'icosahedron',
  group: 'octahedron',
  text_chunk: 'sphere',
};

export function getShapeType(label: string): number {
  const key = label.toLowerCase();
  const shape = LABEL_SHAPES[key] ?? guessShape(label);
  return SHAPE_TYPES.indexOf(shape);
}

function guessShape(label: string): NodeShapeType {
  let hash = 0;
  for (let i = 0; i < label.length; i++) {
    hash = label.charCodeAt(i) + ((hash << 5) - hash);
  }
  return SHAPE_TYPES[Math.abs(hash) % SHAPE_TYPES.length];
}

function hashColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = ((hash % 360) + 360) % 360;
  return `hsl(${hue}, 65%, 55%)`;
}

const _colorCache = new Map<string, string>();
const _emissiveCache = new Map<string, string>();

export function getNodeColor(label: string): string {
  const key = label.toLowerCase();
  if (LABEL_COLORS[key]) return LABEL_COLORS[key].base;

  if (!_colorCache.has(key)) {
    _colorCache.set(key, hashColor(key));
  }
  return _colorCache.get(key)!;
}

export function getNodeEmissiveColor(label: string): string {
  const key = label.toLowerCase();
  if (LABEL_COLORS[key]) return LABEL_COLORS[key].emissive;

  if (!_emissiveCache.has(key)) {
    const base = getNodeColor(label);
    _emissiveCache.set(key, base);
  }
  return _emissiveCache.get(key)!;
}

export function getNodeColorPair(label: string): LabelColorPair {
  const key = label.toLowerCase();
  if (LABEL_COLORS[key]) return LABEL_COLORS[key];
  return { base: getNodeColor(label), emissive: getNodeEmissiveColor(label) };
}

// ---------------------------------------------------------------------------
// Community color palette — used by the graph when the 'community' lens is
// active. 20 distinct hues that remain distinguishable even for color-blind
// users (varied in both hue and lightness).
// ---------------------------------------------------------------------------

export const COMMUNITY_COLORS: string[] = [
  '#a78bfa', // violet
  '#f472b6', // pink
  '#fb923c', // orange
  '#34d399', // emerald
  '#60a5fa', // blue
  '#fbbf24', // amber
  '#2dd4bf', // teal
  '#e879f9', // fuchsia
  '#f87171', // red
  '#38bdf8', // sky
  '#a3e635', // lime
  '#c084fc', // purple
  '#fb7185', // rose
  '#22d3ee', // cyan
  '#fdba74', // light orange
  '#818cf8', // indigo
  '#4ade80', // green
  '#facc15', // yellow
  '#f0abfc', // light fuchsia
  '#67e8f9', // light cyan
];

const _communityColorCache = new Map<number, string>();

export function getCommunityColor(communityId: number | undefined): string {
  if (communityId === undefined) return '#6b7280'; // gray for unknown
  if (!_communityColorCache.has(communityId)) {
    const color = COMMUNITY_COLORS[communityId % COMMUNITY_COLORS.length];
    _communityColorCache.set(communityId, color);
  }
  return _communityColorCache.get(communityId)!;
}

const _communityEmissiveCache = new Map<number, string>();

export function getCommunityEmissiveColor(communityId: number | undefined): string {
  if (communityId === undefined) return '#9ca3af';
  if (!_communityEmissiveCache.has(communityId)) {
    // Lighten the base color for emissive
    const base = getCommunityColor(communityId);
    _communityEmissiveCache.set(communityId, base);
  }
  return _communityEmissiveCache.get(communityId)!;
}
