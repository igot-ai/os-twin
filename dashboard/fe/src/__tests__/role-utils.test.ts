/**
 * role-utils.test.ts — Unit tests for parseRolesFromMarkdown().
 *
 * Mirrors the role-parsing test matrix from PlanParser.Tests.ps1 and
 * test_parse_roles_markdown.py to ensure the TypeScript frontend parser
 * stays aligned with the canonical PowerShell and Python parsers.
 */

import { describe, it, expect } from 'vitest';
import {
  parseRolesFromMarkdown,
  getRoleColor,
  getRoleInitial,
  getRoleInitials,
  roleColorMap,
} from '@/lib/role-utils';

// ─── Backward compatibility: plain format (no @) ─────────────────────

describe('parseRolesFromMarkdown – plain format', () => {
  it('parses comma-separated roles', () => {
    expect(parseRolesFromMarkdown('Roles: engineer, qa')).toEqual(['engineer', 'qa']);
  });

  it('parses singular Role: directive', () => {
    expect(parseRolesFromMarkdown('Role: engineer')).toEqual(['engineer']);
  });

  it('parses a single role', () => {
    expect(parseRolesFromMarkdown('Roles: designer')).toEqual(['designer']);
  });

  it('parses roles with instance suffix', () => {
    expect(parseRolesFromMarkdown('Roles: engineer:be, engineer:fe')).toEqual([
      'engineer:be',
      'engineer:fe',
    ]);
  });

  it('strips trailing comments in parentheses', () => {
    expect(parseRolesFromMarkdown('Roles: engineer, qa (primary roles)')).toEqual([
      'engineer',
      'qa',
    ]);
  });

  it('ignores placeholder angle-bracket names', () => {
    expect(parseRolesFromMarkdown('Roles: <role-name>')).toEqual([]);
  });

  it('returns empty for empty text', () => {
    expect(parseRolesFromMarkdown('')).toEqual([]);
  });

  it('returns empty when no Roles: directive exists', () => {
    expect(parseRolesFromMarkdown('# Plan\n\nSome text without any roles.')).toEqual([]);
  });

  it('deduplicates while preserving order', () => {
    expect(parseRolesFromMarkdown('Roles: engineer, qa, engineer')).toEqual(['engineer', 'qa']);
  });
});

// ─── @-prefixed format ───────────────────────────────────────────────

describe('parseRolesFromMarkdown – @-prefixed format', () => {
  it('parses @-prefixed roles and strips @', () => {
    const result = parseRolesFromMarkdown('Roles: @engineer, @qa');
    expect(result).toEqual(['engineer', 'qa']);
    expect(result).not.toContain('@engineer');
    expect(result).not.toContain('@qa');
  });

  it('parses mixed @ and plain names', () => {
    expect(parseRolesFromMarkdown('Roles: @engineer, qa, @designer')).toEqual([
      'engineer',
      'qa',
      'designer',
    ]);
  });

  it('parses space-separated @ roles', () => {
    expect(parseRolesFromMarkdown('Roles: @engineer @qa @designer')).toEqual([
      'engineer',
      'qa',
      'designer',
    ]);
  });

  it('parses @ roles with instance suffix', () => {
    expect(parseRolesFromMarkdown('Roles: @engineer:fe, @qa')).toEqual(['engineer:fe', 'qa']);
  });

  it('ignores trailing ellipsis', () => {
    const result = parseRolesFromMarkdown('Roles: @qa, ...');
    expect(result).toEqual(['qa']);
    expect(result).not.toContain('...');
  });

  it('deduplicates @ roles', () => {
    expect(parseRolesFromMarkdown('Roles: @engineer, @qa, @engineer')).toEqual([
      'engineer',
      'qa',
    ]);
  });
});

// ─── Markdown formatting variants ────────────────────────────────────

describe('parseRolesFromMarkdown – markdown formatting', () => {
  it('parses ### Roles: heading format', () => {
    expect(parseRolesFromMarkdown('### Roles: @engineer, @qa')).toEqual(['engineer', 'qa']);
  });

  it('parses ## Roles: heading format', () => {
    expect(parseRolesFromMarkdown('## Roles: engineer, qa')).toEqual(['engineer', 'qa']);
  });

  it('parses #### Roles: heading format', () => {
    expect(parseRolesFromMarkdown('#### Roles: @designer')).toEqual(['designer']);
  });

  it('parses **Roles**: bold format', () => {
    expect(parseRolesFromMarkdown('**Roles**: @designer')).toEqual(['designer']);
  });

  it('parses *Role*: italic format', () => {
    expect(parseRolesFromMarkdown('*Role*: @architect')).toEqual(['architect']);
  });

  it('parses **Role**: bold singular', () => {
    expect(parseRolesFromMarkdown('**Role**: engineer')).toEqual(['engineer']);
  });
});

// ─── Multi-epic plan parsing ─────────────────────────────────────────

describe('parseRolesFromMarkdown – multi-epic', () => {
  it('collects roles from multiple Roles: lines', () => {
    const md = [
      '## EPIC-001 — Auth',
      'Roles: @engineer, @qa',
      '',
      '## EPIC-002 — Frontend',
      'Roles: @designer, @engineer',
    ].join('\n');
    expect(parseRolesFromMarkdown(md)).toEqual(['engineer', 'qa', 'designer']);
  });

  it('handles mixed formats across epics', () => {
    const md = [
      '## EPIC-001',
      '### Roles: @engineer:be',
      '',
      '## EPIC-002',
      'Roles: engineer:fe',
    ].join('\n');
    expect(parseRolesFromMarkdown(md)).toEqual(['engineer:be', 'engineer:fe']);
  });
});

// ─── Edge cases ──────────────────────────────────────────────────────

describe('parseRolesFromMarkdown – edge cases', () => {
  it('parses roles in the middle of a document', () => {
    const md = [
      '# Plan: Test',
      '',
      'Some description text.',
      '',
      '## EPIC-001 — Setup',
      'Objective: Do things',
      'Roles: @engineer, @qa',
      'Working_dir: src/',
    ].join('\n');
    expect(parseRolesFromMarkdown(md)).toEqual(['engineer', 'qa']);
  });

  it('does not match inline "Roles:" with arbitrary prefix', () => {
    const md = 'The Roles: engineer, qa are defined.';
    expect(parseRolesFromMarkdown(md)).toEqual([]);
  });

  it('handles extra whitespace around names', () => {
    expect(parseRolesFromMarkdown('Roles:   @engineer ,  @qa  , @designer  ')).toEqual([
      'engineer',
      'qa',
      'designer',
    ]);
  });

  it('handles comma and space mixed separators', () => {
    expect(parseRolesFromMarkdown('Roles: @engineer, @qa @designer')).toEqual([
      'engineer',
      'qa',
      'designer',
    ]);
  });
});

// ─── Utility functions ──────────────────────────────────────────────

describe('getRoleColor', () => {
  it('returns mapped color for known roles', () => {
    expect(getRoleColor('engineer')).toBe('#3b82f6');
    expect(getRoleColor('qa')).toBe('#10b981');
    expect(getRoleColor('designer')).toBe('#ec4899');
  });

  it('returns fallback for unknown roles', () => {
    expect(getRoleColor('unknown-role')).toBe('#6366f1');
  });

  it('returns fallback for empty string', () => {
    expect(getRoleColor('')).toBe('#6366f1');
  });
});

describe('getRoleInitial', () => {
  it('returns uppercase first letter', () => {
    expect(getRoleInitial('engineer')).toBe('E');
    expect(getRoleInitial('qa')).toBe('Q');
  });

  it('returns ? for empty string', () => {
    expect(getRoleInitial('')).toBe('?');
  });
});

describe('getRoleInitials', () => {
  it('returns two-char initials for single word', () => {
    expect(getRoleInitials('engineer')).toBe('EN');
  });

  it('returns first+last initials for multi-word', () => {
    expect(getRoleInitials('frontend-engineer')).toBe('FE');
  });

  it('returns ?? for empty string', () => {
    expect(getRoleInitials('')).toBe('??');
  });
});

describe('roleColorMap', () => {
  it('has entries for core roles', () => {
    expect(roleColorMap).toHaveProperty('engineer');
    expect(roleColorMap).toHaveProperty('qa');
    expect(roleColorMap).toHaveProperty('architect');
    expect(roleColorMap).toHaveProperty('manager');
    expect(roleColorMap).toHaveProperty('designer');
  });
});
