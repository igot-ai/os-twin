import { describe, it, expect } from 'vitest';
import { extractPlan } from './extract-plan';

// ---------------------------------------------------------------------------
// Helpers — reusable plan fragments
// ---------------------------------------------------------------------------

/** Minimal well-formed plan (no lifecycle code blocks). */
const SIMPLE_PLAN = `# Plan: Simple Feature

> Created: 2026-04-12T00:00:00Z
> Status: draft

## Goal

Build a simple feature.

## EPIC-001 — Research

Roles: researcher

### Tasks
- [ ] TASK-001 — Gather data`;

/** Realistic plan with multiple lifecycle ```text blocks (the bug trigger). */
const FULL_PLAN_WITH_LIFECYCLES = `# Plan: Online Casino Platform

> Created: 2026-04-12T00:00:00Z
> Status: draft
> Project: /tmp/casino

## Config

working_dir: /tmp/casino

---

## Goal

Build a full-stack online casino with provably fair games.

## EPIC-001 — System Architecture & Design

Roles: architect
Objective: Design the foundational architecture.
Lifecycle:
\`\`\`text
pending → architect → qa ─┬─► passed → signoff
              ▲            │
              └─ architect ◄┘ (on fail → fixing)
\`\`\`
Skills: architecture-design, documentation, cryptography
Capabilities: architecture

### Definition of Done
- [ ] System Architecture Document (SAD) finalized.
- [ ] API Specifications (OpenAPI/Swagger) drafted.

### Tasks
- [ ] TASK-001 — Design high-level system architecture.
- [ ] TASK-002 — Define tech stack.

### Acceptance criteria:
- Architecture supports horizontal scaling.

depends_on: []

## EPIC-002 — User Identity & KYC

Roles: engineer, qa
Objective: Implement secure authentication and KYC.
Lifecycle:
\`\`\`text
pending → engineer → qa ─┬─► passed → signoff
              ▲          │
              └─ engineer ◄┘ (on fail → fixing)
\`\`\`
Skills: authentication, jwt

### Definition of Done
- [ ] Authentication system functional.

### Tasks
- [ ] TASK-001 — Implement JWT-based auth.

depends_on: [EPIC-001]

## EPIC-003 — Wallet & Payments

Roles: database-architect, engineer, qa
Objective: Build a secure financial core.
Lifecycle:
\`\`\`text
pending → database-architect → engineer → qa ─┬─► passed → signoff
               ▲                    ▲         │
               └────────── database-architect ◄┘ (on schema fail)
\`\`\`
Skills: sql, payment-gateways

### Definition of Done
- [ ] Double-entry bookkeeping implemented.

### Tasks
- [ ] TASK-001 — Design SQL schema.

depends_on: [EPIC-001]`;

// ═══════════════════════════════════════════════════════════════════════════
// Strategy 1 — ```markdown fenced code block extraction
// ═══════════════════════════════════════════════════════════════════════════

describe('extractPlan — Strategy 1: ```markdown code block', () => {
  it('extracts a simple plan from a ```markdown block', () => {
    const ai = `Here is your plan:\n\n\`\`\`markdown\n${SIMPLE_PLAN}\n\`\`\`\n\nLet me know if you want changes.`;
    expect(extractPlan(ai)).toBe(SIMPLE_PLAN);
  });

  it('extracts from a ```md block', () => {
    const ai = `\`\`\`md\n${SIMPLE_PLAN}\n\`\`\``;
    expect(extractPlan(ai)).toBe(SIMPLE_PLAN);
  });

  it('preserves EPIC-001 heading and lifecycle when plan has nested ```text blocks', () => {
    const ai = `Here's the full plan:\n\n\`\`\`markdown\n${FULL_PLAN_WITH_LIFECYCLES}\n\`\`\``;
    const result = extractPlan(ai);

    // Must start with the plan title — NOT mid-body
    expect(result).toMatch(/^# Plan: Online Casino Platform/);
    // Header metadata preserved
    expect(result).toContain('> Created: 2026-04-12');
    expect(result).toContain('> Status: draft');
    // Config + Goal preserved
    expect(result).toContain('## Config');
    expect(result).toContain('## Goal');
    // EPIC-001 heading preserved (the original bug dropped this)
    expect(result).toContain('## EPIC-001 — System Architecture & Design');
    expect(result).toContain('Roles: architect');
    // Lifecycle content preserved inside nested code block
    expect(result).toContain('pending → architect → qa');
    // Fields after lifecycle preserved
    expect(result).toContain('Skills: architecture-design, documentation, cryptography');
    // All epics present
    expect(result).toContain('## EPIC-002 — User Identity & KYC');
    expect(result).toContain('## EPIC-003 — Wallet & Payments');
    // Last epic's lifecycle content also preserved
    expect(result).toContain('pending → database-architect → engineer → qa');
    // depends_on not mangled
    expect(result).toContain('depends_on: [EPIC-001]');
  });

  it('handles multiple nested code block types (```text, ```yaml, ```json)', () => {
    const plan = [
      '# Plan: Multi-Fence',
      '',
      '## EPIC-001 — Test',
      'Lifecycle:',
      '```text',
      'pending → engineer',
      '```',
      'Config:',
      '```yaml',
      'key: value',
      '```',
      'Schema:',
      '```json',
      '{ "ok": true }',
      '```',
    ].join('\n');

    const ai = `\`\`\`markdown\n${plan}\n\`\`\``;
    const result = extractPlan(ai);
    expect(result).toBe(plan);
  });

  it('handles deeply nested code blocks (fence inside fence inside fence)', () => {
    const plan = [
      '# Plan: Deep Nesting',
      '',
      '## EPIC-001 — Outer',
      '```text',
      'level 1',
      '```',
      '## EPIC-002 — Inner',
      '```yaml',
      'level: 1',
      '```',
    ].join('\n');

    const ai = `Notes:\n\n\`\`\`markdown\n${plan}\n\`\`\`\n\nDone.`;
    expect(extractPlan(ai)).toBe(plan);
  });

  it('ignores bare ``` inside plan and does not misidentify it as the outer closing fence', () => {
    // Regression: the old regex would match a bare ``` (lifecycle closing) as its opening
    const plan = [
      '# Plan: Fence Regression',
      '',
      '## EPIC-001 — Arch',
      'Lifecycle:',
      '```text',
      'pending → architect',
      '```',                    // <-- old regex matched this as opening!
      'Skills: architecture',
      '',
      '## EPIC-002 — Build',
      'Lifecycle:',
      '```text',
      'pending → engineer',
      '```',                    // <-- old regex matched this as closing!
      'Skills: engineering',
    ].join('\n');

    const ai = `\`\`\`markdown\n${plan}\n\`\`\``;
    const result = extractPlan(ai);

    // Must get the FULL plan, not just "Skills: architecture ... Skills: engineering"
    expect(result).toContain('# Plan: Fence Regression');
    expect(result).toContain('## EPIC-001 — Arch');
    expect(result).toContain('## EPIC-002 — Build');
    expect(result).toContain('pending → architect');
    expect(result).toContain('pending → engineer');
  });

  it('returns raw content when ```markdown block has no closing fence', () => {
    const ai = `\`\`\`markdown\n# Plan: Unclosed\n## EPIC-001 — Test`;
    // No closing ``` → strategy 1 fails → falls through to strategy 2
    const result = extractPlan(ai);
    expect(result).toContain('# Plan: Unclosed');
  });

  it('handles trailing whitespace after closing fence', () => {
    const ai = `\`\`\`markdown\n${SIMPLE_PLAN}\n\`\`\`   \n\nSome trailing text.`;
    // The closing ``` has trailing spaces — trimmed line is still "```"
    expect(extractPlan(ai)).toBe(SIMPLE_PLAN);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Strategy 2 — content starts with "# Plan:"
// ═══════════════════════════════════════════════════════════════════════════

describe('extractPlan — Strategy 2: starts with # Plan:', () => {
  it('returns trimmed content when it starts directly with # Plan:', () => {
    const result = extractPlan(`  ${SIMPLE_PLAN}  `);
    expect(result).toBe(SIMPLE_PLAN);
  });

  it('handles plan with lifecycle blocks (no code fence wrapper)', () => {
    const result = extractPlan(FULL_PLAN_WITH_LIFECYCLES);
    expect(result).toBe(FULL_PLAN_WITH_LIFECYCLES);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Strategy 3 — "# Plan:" found somewhere in content
// ═══════════════════════════════════════════════════════════════════════════

describe('extractPlan — Strategy 3: # Plan: found mid-content', () => {
  it('extracts from the # Plan: header when preceded by conversational text', () => {
    const ai = `I've updated the plan based on your feedback. Here it is:\n\n${SIMPLE_PLAN}`;
    const result = extractPlan(ai);
    expect(result).toBe(SIMPLE_PLAN);
  });

  it('extracts full plan with lifecycles when preceded by conversational text', () => {
    const ai = `Sure! Here's the revised plan:\n\n${FULL_PLAN_WITH_LIFECYCLES}`;
    const result = extractPlan(ai);
    expect(result).toMatch(/^# Plan: Online Casino Platform/);
    expect(result).toContain('## EPIC-001');
    expect(result).toContain('## EPIC-003');
  });

  it('captures everything after # Plan: including trailing content', () => {
    const ai = `Explanation.\n\n# Plan: Inline\n\n## Goal\n\nDo stuff.\n\nSome trailing notes.`;
    const result = extractPlan(ai);
    expect(result).toMatch(/^# Plan: Inline/);
    expect(result).toContain('## Goal');
    expect(result).toContain('Some trailing notes.');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Strategy 4 — fallback (no plan header, no code block)
// ═══════════════════════════════════════════════════════════════════════════

describe('extractPlan — Strategy 4: fallback', () => {
  it('returns raw content when nothing matches', () => {
    const raw = 'Just some random AI response without a plan.';
    expect(extractPlan(raw)).toBe(raw);
  });

  it('returns empty string for empty input', () => {
    expect(extractPlan('')).toBe('');
  });

  it('returns whitespace-only input as-is', () => {
    expect(extractPlan('   ')).toBe('   ');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Strategy priority — ensures correct strategy wins
// ═══════════════════════════════════════════════════════════════════════════

describe('extractPlan — strategy priority', () => {
  it('prefers ```markdown extraction over raw # Plan: in surrounding text', () => {
    const planInBlock = '# Plan: Inside Block\n\n## Goal\n\nBlock content.';
    const ai = `# Plan: Outside Block\n\nWrong plan.\n\n\`\`\`markdown\n${planInBlock}\n\`\`\``;
    const result = extractPlan(ai);
    // The ```markdown block content should win
    expect(result).toBe(planInBlock);
  });

  it('falls through to strategy 2 when ```markdown has no closing fence', () => {
    const ai = `\`\`\`markdown\n# Plan: Broken Block`;
    const result = extractPlan(ai);
    // Strategy 1 fails (no closing ```), strategy 2 won't match (starts with ```),
    // strategy 3 finds # Plan:
    expect(result).toContain('# Plan: Broken Block');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Regression test — the exact bug scenario from the screenshot
// ═══════════════════════════════════════════════════════════════════════════

describe('extractPlan — regression: EPIC-001 header must not be dropped', () => {
  it('preserves full plan when AI wraps response in ```markdown with lifecycle blocks (original bug)', () => {
    // This is the exact scenario that caused the bug:
    // The AI wraps the plan in ```markdown, the plan has lifecycle ```text blocks,
    // the old greedy regex matched the first bare ``` (lifecycle close) as its
    // opening and dropped everything before it.
    const fullPlan = [
      '# Plan: Casino Platform',
      '',
      '> Created: 2026-04-12T00:00:00Z',
      '> Status: draft',
      '> Project: /tmp/casino',
      '',
      '## Config',
      '',
      'working_dir: /tmp/casino',
      '',
      '---',
      '',
      '## Goal',
      '',
      'Build a provably fair online casino.',
      '',
      '## EPIC-001 — System Architecture & Design',
      '',
      'Roles: architect',
      'Objective: Design the foundational architecture.',
      'Lifecycle:',
      '```text',
      'pending → architect → qa ─┬─► passed → signoff',
      '              ▲            │',
      '              └─ architect ◄┘ (on fail → fixing)',
      '```',
      'Skills: architecture-design, documentation, cryptography',
      'Capabilities: architecture',
      '',
      '### Definition of Done',
      '- [ ] SAD finalized.',
      '',
      '### Tasks',
      '- [ ] TASK-001 — Design architecture.',
      '- [ ] TASK-002 — Define tech stack.',
      '- [ ] TASK-003 — Document Provably Fair requirements.',
      '',
      'depends_on: []',
      '',
      '## EPIC-006 — Security Audit & Launch Prep',
      '',
      'Roles: audit, engineer, qa, technical-writer',
      'Objective: Validate platform security.',
      'Lifecycle:',
      '```text',
      'pending → audit → engineer → qa → technical-writer ─┬─► passed',
      '            ▲          ▲      ▲                     │',
      '            └───────────────────────── audit ◄──────┘',
      '```',
      'Skills: penetration-testing',
      '',
      '### Tasks',
      '- [ ] TASK-001 — Conduct penetration testing.',
      '- [ ] TASK-002 — Stress testing.',
      '- [ ] TASK-003 — Deployment runbooks.',
      '',
      'depends_on: [EPIC-005]',
    ].join('\n');

    const aiResponse = `Here's the complete plan for your casino platform:\n\n\`\`\`markdown\n${fullPlan}\n\`\`\`\n\nClick "Apply to Editor" to use this plan.`;

    const result = extractPlan(aiResponse);

    // ── The original bug would fail ALL of these ──
    expect(result).toMatch(/^# Plan: Casino Platform/);
    expect(result).toContain('> Created: 2026-04-12');
    expect(result).toContain('## Config');
    expect(result).toContain('## Goal');
    expect(result).toContain('## EPIC-001 — System Architecture & Design');
    expect(result).toContain('Roles: architect');
    expect(result).toContain('pending → architect → qa');
    expect(result).toContain('Skills: architecture-design, documentation, cryptography');
    expect(result).toContain('## EPIC-006 — Security Audit & Launch Prep');
    expect(result).toContain('depends_on: [EPIC-005]');

    // Must NOT contain the AI's conversational wrapper text
    expect(result).not.toContain("Here's the complete plan");
    expect(result).not.toContain('Click "Apply to Editor"');
  });

  it('does NOT start with "Skills:" (the old broken behavior)', () => {
    const planWithLifecycle = [
      '# Plan: Test',
      '',
      '## EPIC-001 — Arch',
      'Lifecycle:',
      '```text',
      'pending → arch',
      '```',
      'Skills: architecture',
    ].join('\n');

    const ai = `\`\`\`markdown\n${planWithLifecycle}\n\`\`\``;
    const result = extractPlan(ai);

    // Old bug: result would start with "Skills: architecture"
    expect(result).not.toMatch(/^Skills:/);
    expect(result).toMatch(/^# Plan: Test/);
  });
});
