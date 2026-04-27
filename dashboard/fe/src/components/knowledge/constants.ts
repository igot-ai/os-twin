/**
 * Shared constants for Knowledge UI components.
 */

/** Color palette for entity label types (used in graph nodes, query results, etc.) */
export const LABEL_COLORS: Record<string, string> = {
  entity: '#3b82f6',
  person: '#8b5cf6',
  organization: '#ec4899',
  location: '#f97316',
  event: '#10b981',
  concept: '#06b6d4',
  document: '#6366f1',
  default: '#6b7280',
};

/** Get the color for a given node/entity label. Falls back to grey. */
export function getNodeColor(label: string): string {
  return LABEL_COLORS[label.toLowerCase()] || LABEL_COLORS.default;
}
