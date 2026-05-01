import { parseEpicMarkdown, serializeEpicMarkdown } from '../lib/epic-parser';

const sampleMarkdown = `# PLAN: Enhanced Markdown Preview

This is the preamble.

## EPIC-001 — Feature Title
**Phase:** 1
**Owner:** engineer
**Priority:** P0

### Description
This is a description with **bold** and *italic*.

### Definition of Done
- [ ] Item 1
- [x] Item 2

### Tasks
- [ ] **T-G001.1** — Task 1
  AC: Acceptance criteria here.
- [x] **T-G001.2** — Task 2
  Some body here.

### Acceptance Criteria
- [ ] AC 1

depends_on: [EPIC-000]

## EPIC-002 — Another Feature
**Phase:** 1

### Description
Another description.

---
Verification Plan:
- Test 1
`;

describe('Epic Markdown Parser & Serializer', () => {
  it('should preserve content in a round-trip', () => {
    const doc = parseEpicMarkdown(sampleMarkdown);
    const serialized = serializeEpicMarkdown(doc);
    
    // Check if serialized content matches original (ignoring potential trailing newlines)
    expect(serialized.trim()).toBe(sampleMarkdown.trim());
  });

  it('should parse EPICs correctly', () => {
    const doc = parseEpicMarkdown(sampleMarkdown);
    expect(doc.epics.length).toBe(2);
    expect(doc.epics[0].ref).toBe('EPIC-001');
    expect(doc.epics[0].title).toBe('Feature Title');
    expect(doc.epics[0].frontmatter.get('Phase')).toBe('1');
    expect(doc.epics[0].depends_on).toContain('EPIC-000');
  });

  it('should parse tasks correctly', () => {
    const doc = parseEpicMarkdown(sampleMarkdown);
    const epic1 = doc.epics[0];
    const tasksSection = epic1.sections.find(s => s.heading === 'Tasks');
    expect(tasksSection).toBeDefined();
    expect(tasksSection?.tasks?.length).toBe(2);
    expect(tasksSection?.tasks?.[0].id).toBe('T-G001.1');
    expect(tasksSection?.tasks?.[0].completed).toBe(false);
    expect(tasksSection?.tasks?.[1].completed).toBe(true);
  });
});

// ── Regression test: Roles duplication ────────────────────────────────

describe('Roles duplication regression', () => {
  const rolesMarkdown = `# Plan: KẾ HOẠCH KIỂM TOÁN

## EPIC-001 — Setup
Roles: @engineer, @audit

### Definition of Done
- [ ] Data Quality Score ≥ 90%

depends_on: []

## EPIC-002 — Dashboard
Roles: @engineer, @audit

### Definition of Done
- [ ] Dashboard renders correctly

depends_on: [EPIC-001]
`;

  it('should not duplicate Roles lines on round-trip', () => {
    const doc = parseEpicMarkdown(rolesMarkdown);
    const serialized = serializeEpicMarkdown(doc);

    // Count how many "Roles:" lines exist
    const rolesCount = (serialized.match(/^Roles:/gm) || []).length;
    const boldRolesCount = (serialized.match(/^\*\*Roles\*\*/gm) || []).length;
    const totalRolesLines = rolesCount + boldRolesCount;

    // Should have exactly 2 Roles lines (one per EPIC)
    expect(totalRolesLines).toBe(2);
  });

  it('should not accumulate Roles lines over multiple cycles', () => {
    let md = rolesMarkdown;

    // Simulate 5 parse→serialize cycles (as happens on repeated saves)
    for (let i = 0; i < 5; i++) {
      const doc = parseEpicMarkdown(md);
      md = serializeEpicMarkdown(doc);
    }

    const rolesCount = (md.match(/Roles:/gm) || []).length;
    const boldRolesCount = (md.match(/\*\*Roles\*\*/gm) || []).length;
    const totalRolesLines = rolesCount + boldRolesCount;

    // Should still be exactly 2 Roles lines after 5 cycles
    expect(totalRolesLines).toBe(2);
  });

  it('should preserve Roles in frontmatter correctly', () => {
    const doc = parseEpicMarkdown(rolesMarkdown);
    expect(doc.epics[0].frontmatter.get('Roles')).toBe('engineer, audit');
    expect(doc.epics[1].frontmatter.get('Roles')).toBe('engineer, audit');
  });
});
