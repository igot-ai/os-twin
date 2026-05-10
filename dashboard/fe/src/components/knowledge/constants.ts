/**
 * Shared constants for Knowledge UI components.
 */

/** Known color palette for common entity label types */
export const LABEL_COLORS: Record<string, string> = {
  entity: '#3b82f6',
  person: '#8b5cf6',
  organization: '#ec4899',
  location: '#f97316',
  event: '#10b981',
  concept: '#06b6d4',
  document: '#6366f1',
  date: '#eab308',
  product: '#14b8a6',
  technology: '#a855f7',
  country: '#f43f5e',
  city: '#0ea5e9',
  money: '#84cc16',
  law: '#d946ef',
  media: '#fb923c',
  group: '#22d3ee',
  text_chunk: '#94a3b8',
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

/**
 * Generate a deterministic HSL color from a string.
 * Uses a simple hash to distribute hues evenly, ensuring
 * each unique label always gets the same distinct color.
 */
function hashColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = ((hash % 360) + 360) % 360;
  return `hsl(${hue}, 65%, 55%)`;
}

/** Runtime cache so we only compute once per label */
const _colorCache = new Map<string, string>();

/** Get the color for a given node/entity label. Falls back to a deterministic hash color. */
export function getNodeColor(label: string): string {
  const key = label.toLowerCase();
  if (LABEL_COLORS[key]) return LABEL_COLORS[key];

  if (!_colorCache.has(key)) {
    _colorCache.set(key, hashColor(key));
  }
  return _colorCache.get(key)!;
}
