/** Role → color mapping for badges and icons */
export const roleColorMap: Record<string, string> = {
  architect: '#8b5cf6',
  manager: '#64748b',
  engineer: '#3b82f6',
  'frontend-engineer': '#3b82f6',
  'frontend-ui-engineer': '#ec4899',
  'frontend-dag-engineer': '#06b6d4',
  'frontend-realtime-engineer': '#f59e0b',
  'frontend-interaction-engineer': '#10b981',
  'frontend-accessibility-engineer': '#ef4444',
  'build-integration-engineer': '#14b8a6',
  qa: '#10b981',
  'data-analyst': '#6366f1',
  copywriter: '#f59e0b',
  designer: '#ec4899',
  auditor: '#8b5cf6',
  system: '#38bdf8',
};

/** Get first letter of role for the badge, e.g. "engineer" → "E" */
export function getRoleInitial(role: string): string {
  if (!role) return '?';
  // Use first character of first word
  return role.charAt(0).toUpperCase();
}

/** Robustly derive a color for any role string */
export function getRoleColor(role: string): string {
  if (!role) return '#6366f1';
  const normalized = role.toLowerCase();
  return roleColorMap[normalized] || '#6366f1';
}

/** Derived initials for more complex labels, e.g. "Frontend Engineer" -> "FE" */
export function getRoleInitials(role: string): string {
  if (!role) return '??';
  const words = role.split(/[ -]/);
  if (words.length > 1) {
    return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  }
  return role.substring(0, 2).toUpperCase();
}

/**
 * Parse role names from `Roles: a, b, c` directives in markdown content.
 * Matches the same pattern used by the plan engine (Start-Plan.ps1).
 */
export function parseRolesFromMarkdown(body: string): string[] {
  const roles: string[] = [];
  const re = /^Roles?:\s*(.+)$/gm;
  let match;
  while ((match = re.exec(body)) !== null) {
    const line = match[1].replace(/\(.*$/, ''); // strip trailing comments
    for (const part of line.split(',')) {
      const name = part.trim();
      if (name && /^[a-zA-Z0-9]/.test(name) && !/^<.*>$/.test(name)) {
        roles.push(name);
      }
    }
  }
  // dedupe, preserve order
  return [...new Set(roles)];
}
