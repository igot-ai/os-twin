import { describe, it, expect } from 'vitest';
import { parseEpicMarkdown, serializeEpicMarkdown } from './epic-parser';
import * as fs from 'fs';
import * as path from 'path';

describe('Epic Parser & Serializer', () => {
  it('should round-trip a simple document', () => {
    const md = `# PLAN: Simple
Preamble text.

---

## EPIC-001 — First Epic
**Phase:** 1
**Owner:** engineer

### Description
Some description here.

- [ ] Item 1
- [x] Item 2

#### Tasks
- [ ] TASK-001 — Setup
  AC: Ready.

---

## EPIC-002 — Second Epic
**Phase:** 2
**Owner:** qa

### Description
Another description.
`;
    const doc = parseEpicMarkdown(md);
    const result = serializeEpicMarkdown(doc);
    expect(result).toBe(md);
  });

  it('should extract structured data correctly', () => {
    const md = `## EPIC-001 — First Epic
**Phase:** 1
**Owner:** engineer

### Description
Some description here.

- [ ] Item 1
- [x] Item 2

#### Tasks
- [ ] TASK-001 — Setup
  AC: Ready.
  \`\`\`typescript
  const x = 1;
  \`\`\`

- [x] **T-001.2** — Implementation
  Done.

depends_on: ["EPIC-000"]
`;
    const doc = parseEpicMarkdown(md);
    expect(doc.epics).toHaveLength(1);
    const epic = doc.epics[0];
    expect(epic.ref).toBe('EPIC-001');
    expect(epic.title).toBe('First Epic');
    expect(epic.frontmatter.get('Phase')).toBe('1');
    expect(epic.frontmatter.get('Owner')).toBe('engineer');
    expect(epic.depends_on).toEqual(['EPIC-000']);

    const description = epic.sections.find(s => s.heading === 'Description');
    expect(description).toBeDefined();
    expect(description?.type).toBe('checklist');
    expect(description?.items).toHaveLength(2);
    expect(description?.items?.[0].text).toBe('Item 1');
    expect(description?.items?.[0].checked).toBe(false);
    expect(description?.items?.[1].checked).toBe(true);

    const tasksSection = epic.sections.find(s => s.heading === 'Tasks');
    expect(tasksSection).toBeDefined();
    expect(tasksSection?.type).toBe('tasklist');
    expect(tasksSection?.tasks).toHaveLength(2);
    
    const task1 = tasksSection?.tasks?.[0];
    expect(task1?.id).toBe('TASK-001');
    expect(task1?.title).toBe('Setup');
    expect(task1?.completed).toBe(false);
    expect(task1?.body).toContain('AC: Ready.');
    expect(task1?.body).toContain('\`\`\`typescript');

    const task2 = tasksSection?.tasks?.[1];
    expect(task2?.id).toBe('T-001.2');
    expect(task2?.completed).toBe(true);
    expect(task2?.body.trim()).toBe('Done.');
  });

  it('should extract depends_on from fenced YAML block', () => {
    const md = `## EPIC-002 — YAML Epic
\`\`\`yaml
depends_on: ["EPIC-001"]
\`\`\`
`;
    const doc = parseEpicMarkdown(md);
    expect(doc.epics[0].depends_on).toEqual(['EPIC-001']);
  });

  it('should handle multi-line depends_on in YAML block', () => {
    const md = `## EPIC-002 — YAML Epic
\`\`\`yaml
depends_on:
  - "EPIC-001"
  - 'EPIC-002'
  - EPIC-003
\`\`\`
`;
    const doc = parseEpicMarkdown(md);
    expect(doc.epics[0].depends_on).toEqual(['EPIC-001', 'EPIC-002', 'EPIC-003']);
  });

  it('should extract postamble correctly', () => {
    const md = `# PLAN
## EPIC-001 — Epic
Content
## Postamble
Text
`;
    const doc = parseEpicMarkdown(md);
    expect(doc.epics).toHaveLength(1);
    expect(doc.postamble).toBe('## Postamble\nText\n');
  });

  it('should reflect AST changes in serialized output', () => {
    const md = `## EPIC-001 — First Epic
### Tasks
- [ ] TASK-001 — Setup
`;
    const doc = parseEpicMarkdown(md);
    const tasksSection = doc.epics[0].sections.find(s => s.type === 'tasklist');
    if (tasksSection && tasksSection.tasks) {
      tasksSection.tasks[0].completed = true;
    }
    
    const result = serializeEpicMarkdown(doc);
    expect(result).toContain('- [x] TASK-001 — Setup');
    expect(result).not.toContain('- [ ] TASK-001 — Setup');
  });

  it('should reflect frontmatter changes in serialized output', () => {
    const md = `## EPIC-001 — First Epic
**Phase:** 1
**Owner:** engineer
`;
    const doc = parseEpicMarkdown(md);
    doc.epics[0].frontmatter.set('Phase', '2');
    doc.epics[0].frontmatter.set('Owner', 'qa');
    
    const result = serializeEpicMarkdown(doc);
    expect(result).toContain('**Phase:** 2');
    expect(result).toContain('**Owner:** qa');
    expect(result).not.toContain('**Phase:** 1');
    expect(result).not.toContain('**Owner:** engineer');
  });

  it('should reflect task title and depends_on changes', () => {
    const md = `## EPIC-001 — First Epic
depends_on: [EPIC-000]

### Tasks
- [ ] TASK-001 — Setup
`;
    const doc = parseEpicMarkdown(md);
    doc.epics[0].depends_on = ['EPIC-002', 'EPIC-003'];
    const tasksSection = doc.epics[0].sections.find(s => s.type === 'tasklist');
    if (tasksSection && tasksSection.tasks) {
      tasksSection.tasks[0].title = 'Initial Setup';
    }
    
    const result = serializeEpicMarkdown(doc);
    expect(result).toContain('depends_on: [EPIC-002, EPIC-003]');
    expect(result).toContain('- [ ] TASK-001 — Initial Setup');
  });

  it('should support structural edits (adding/removing tasks)', () => {
    const md = `## EPIC-001 — First Epic
### Tasks
- [ ] TASK-001 — First Task
`;
    const doc = parseEpicMarkdown(md);
    const tasksSection = doc.epics[0].sections.find(s => s.type === 'tasklist');
    if (tasksSection && tasksSection.tasks) {
      // Add a task
      tasksSection.tasks.push({
        id: 'TASK-002',
        title: 'Second Task',
        completed: false,
        body: 'Description for TASK-002.',
        rawHeader: '- [ ] TASK-002 — Second Task'
      });
      // Remove a task
      // tasksSection.tasks.shift(); // Not removing yet to test addition
    }
    
    const result = serializeEpicMarkdown(doc);
    expect(result).toContain('- [ ] TASK-001 — First Task');
    expect(result).toContain('- [ ] TASK-002 — Second Task');
    expect(result).toContain('Description for TASK-002.');
  });

  it('should reflect task body changes', () => {
    const md = `## EPIC-001 — First Epic
### Tasks
- [ ] TASK-001 — Setup
  Original Body.
`;
    const doc = parseEpicMarkdown(md);
    const tasksSection = doc.epics[0].sections.find(s => s.type === 'tasklist');
    if (tasksSection && tasksSection.tasks) {
      tasksSection.tasks[0].body = '  Modified Body.';
    }
    
    const result = serializeEpicMarkdown(doc);
    expect(result).toContain('- [ ] TASK-001 — Setup');
    expect(result).toContain('Modified Body.');
    expect(result).not.toContain('Original Body.');
  });

  it('should handle multi-line depends_on changes correctly', () => {
    const md = `## EPIC-002 — YAML Epic
\`\`\`yaml
depends_on:
  - "EPIC-001"
\`\`\`
`;
    const doc = parseEpicMarkdown(md);
    doc.epics[0].depends_on = ['EPIC-001', 'EPIC-003'];
    
    const result = serializeEpicMarkdown(doc);
    // Ideally it should update the YAML block correctly.
    expect(result).toContain('depends_on: [EPIC-001, EPIC-003]');
  });

  it('should round-trip all repo plan files perfectly', () => {
    const files = [
      '../../../PLAN.md',
      '../../../PLAN-GROWTH.md',
      '../../../refactor-skills-ui.md'
    ];
    for (const f of files) {
      const filePath = path.resolve(__dirname, f);
      if (fs.existsSync(filePath)) {
          const content = fs.readFileSync(filePath, 'utf-8');
          const doc = parseEpicMarkdown(content);
          const result = serializeEpicMarkdown(doc);
          expect(result).toBe(content);
      }
    }
  });

  it('should serialize newly created EPICs with metadata and depends_on', () => {
    const doc = {
      title: 'New Plan',
      preamble: 'Plan goal.',
      epics: [
        {
          ref: 'EPIC-001',
          title: 'Initial Epic',
          headingLevel: 2,
          rawHeading: '## EPIC-001 — Initial Epic',
          frontmatter: new Map([['Owner', 'engineer'], ['Priority', 'P1']]),
          sections: [
            {
              heading: 'Description',
              headingLevel: 3,
              type: 'text' as const,
              content: 'Goal of epic.',
              rawLines: ['Goal of epic.'],
              preamble: [],
              postamble: []
            }
          ],
          depends_on: ['EPIC-000'],
          rawDependsOn: ''
        }
      ],
      postamble: ''
    };
    
    const result = serializeEpicMarkdown(doc as any);
    expect(result).toContain('# New Plan');
    expect(result).toContain('## EPIC-001 — Initial Epic');
    expect(result).toContain('**Owner**: engineer');
    expect(result).toContain('**Priority**: P1');
    expect(result).toContain('depends_on: [EPIC-000]');
    expect(result).toContain('Goal of epic.');
  });
});

// ─── @-prefixed Roles round-trip and modification ──────────────────

describe('Roles @ prefix handling', () => {
  it('should round-trip Roles: @engineer, @qa without spurious changes', () => {
    const md = `## EPIC-001 — Auth
Roles: @engineer, @qa

### Description
Auth setup.
`;
    const doc = parseEpicMarkdown(md);
    const result = serializeEpicMarkdown(doc);
    expect(result).toBe(md);
  });

  it('should round-trip Roles: engineer, qa (no @) without changes', () => {
    const md = `## EPIC-001 — Auth
Roles: engineer, qa

### Description
Auth setup.
`;
    const doc = parseEpicMarkdown(md);
    const result = serializeEpicMarkdown(doc);
    expect(result).toBe(md);
  });

  it('should round-trip **Roles**: @engineer without changes', () => {
    const md = `## EPIC-001 — Auth
**Roles**: @engineer

### Description
Auth setup.
`;
    const doc = parseEpicMarkdown(md);
    const result = serializeEpicMarkdown(doc);
    expect(result).toBe(md);
  });

  it('should strip @ from roles in frontmatter during parsing', () => {
    const md = `## EPIC-001 — Auth
Roles: @engineer, @qa
`;
    const doc = parseEpicMarkdown(md);
    expect(doc.epics[0].frontmatter.get('Roles')).toBe('engineer, qa');
  });

  it('should normalize space-separated @ roles during parsing', () => {
    const md = `## EPIC-001 — Auth
Roles: @engineer @qa @designer
`;
    const doc = parseEpicMarkdown(md);
    expect(doc.epics[0].frontmatter.get('Roles')).toBe('engineer, qa, designer');
  });

  it('should strip @ from plain Roles: format too (no-op)', () => {
    const md = `## EPIC-001 — Auth
Roles: engineer, qa
`;
    const doc = parseEpicMarkdown(md);
    expect(doc.epics[0].frontmatter.get('Roles')).toBe('engineer, qa');
  });

  it('should output @-prefixed roles when a role is added', () => {
    const md = `## EPIC-001 — Auth
Roles: @engineer, @qa

### Description
Auth setup.
`;
    const doc = parseEpicMarkdown(md);
    // Simulate user adding a role via the UI
    const roles = doc.epics[0].frontmatter.get('Roles')!.split(', ');
    roles.push('designer');
    doc.epics[0].frontmatter.set('Roles', roles.join(', '));

    const result = serializeEpicMarkdown(doc);
    expect(result).toContain('Roles: @engineer, @qa, @designer');
  });

  it('should output @-prefixed roles when a role is removed', () => {
    const md = `## EPIC-001 — Auth
Roles: @engineer, @qa, @designer

### Description
Auth setup.
`;
    const doc = parseEpicMarkdown(md);
    // Simulate user removing a role
    const roles = doc.epics[0].frontmatter.get('Roles')!.split(', ').filter(r => r !== 'qa');
    doc.epics[0].frontmatter.set('Roles', roles.join(', '));

    const result = serializeEpicMarkdown(doc);
    expect(result).toContain('Roles: @engineer, @designer');
    expect(result).not.toContain('@qa');
  });

  it('should upgrade plain Roles to @-prefixed when modified', () => {
    const md = `## EPIC-001 — Auth
Roles: engineer, qa

### Description
Auth setup.
`;
    const doc = parseEpicMarkdown(md);
    // Simulate user adding a role — triggers rewrite
    const roles = doc.epics[0].frontmatter.get('Roles')!.split(', ');
    roles.push('designer');
    doc.epics[0].frontmatter.set('Roles', roles.join(', '));

    const result = serializeEpicMarkdown(doc);
    expect(result).toContain('Roles: @engineer, @qa, @designer');
  });

  it('should output @-prefixed roles for bold format when modified', () => {
    const md = `## EPIC-001 — Auth
**Roles**: engineer

### Description
Auth setup.
`;
    const doc = parseEpicMarkdown(md);
    doc.epics[0].frontmatter.set('Roles', 'engineer, qa');

    const result = serializeEpicMarkdown(doc);
    expect(result).toContain('**Roles**: @engineer, @qa');
  });

  it('should output @-prefixed Roles when creating a new epic', () => {
    const doc = {
      title: 'Plan',
      preamble: '',
      epics: [{
        ref: 'EPIC-001',
        title: 'New Epic',
        headingLevel: 2,
        rawHeading: '## EPIC-001 — New Epic',
        frontmatter: new Map([['Roles', 'engineer, qa']]),
        sections: [{
          heading: 'Description',
          headingLevel: 3,
          type: 'text' as const,
          content: 'Goal.',
          rawLines: ['Goal.'],
          preamble: [],
          postamble: [],
        }],
        depends_on: [],
        rawDependsOn: '',
      }],
      postamble: '',
    };

    const result = serializeEpicMarkdown(doc as any);
    expect(result).toContain('**Roles**: @engineer, @qa');
  });

  it('should handle singular Role: with @ prefix', () => {
    const md = `## EPIC-001 — Auth
Role: @engineer
`;
    const doc = parseEpicMarkdown(md);
    expect(doc.epics[0].frontmatter.get('Role')).toBe('engineer');
  });

  it('should ignore trailing ellipsis in Roles', () => {
    const md = `## EPIC-001 — Auth
Roles: @engineer, ...
`;
    const doc = parseEpicMarkdown(md);
    expect(doc.epics[0].frontmatter.get('Roles')).toBe('engineer');
  });
});

// ─── Structural Mutation Tests ─────────────────────────────────────

describe('Structural mutations', () => {
  it('should add an AC section to an EPIC that did not have one', () => {
    const md = `## EPIC-001 — Feature
**Phase:** 1

### Description
Goal of the epic.
`;
    const doc = parseEpicMarkdown(md);
    const epic = doc.epics[0];
    
    // Add a new Acceptance Criteria section
    epic.sections.push({
      heading: 'Acceptance Criteria',
      headingLevel: 3,
      sectionKey: 'acceptance_criteria',
      type: 'checklist',
      content: '',
      items: [
        { text: 'AC 1', checked: false, rawLine: '- [ ] AC 1', prefix: '- [ ] ' },
        { text: 'AC 2', checked: false, rawLine: '- [ ] AC 2', prefix: '- [ ] ' },
      ],
      rawLines: [],
      preamble: ['### Acceptance Criteria'],
      postamble: [],
    });
    
    const result = serializeEpicMarkdown(doc);
    expect(result).toContain('### Acceptance Criteria');
    expect(result).toContain('- [ ] AC 1');
    expect(result).toContain('- [ ] AC 2');
    expect(result).toContain('### Description');
    expect(result).toContain('Goal of the epic.');
  });

  it('should reorder tasks and produce correctly ordered markdown', () => {
    const md = `## EPIC-001 — Feature
### Tasks
- [ ] TASK-001 — First Task
  Body 1.
- [ ] TASK-002 — Second Task
  Body 2.
- [ ] TASK-003 — Third Task
  Body 3.
`;
    const doc = parseEpicMarkdown(md);
    const tasksSection = doc.epics[0].sections.find(s => s.type === 'tasklist');
    
    // Reverse the order of tasks
    expect(tasksSection?.tasks).toBeDefined();
    if (tasksSection && tasksSection.tasks) {
      tasksSection.tasks.reverse();
    }
    
    const result = serializeEpicMarkdown(doc);
    // Third Task should now appear first
    expect(result.indexOf('Third Task')).toBeLessThan(result.indexOf('First Task'));
    expect(result).toContain('- [ ] TASK-003 — Third Task');
    expect(result).toContain('- [ ] TASK-001 — First Task');
    expect(result).toContain('Body 3.');
    expect(result).toContain('Body 1.');
  });

  it('should remove section heading when all items are deleted from a checklist section', () => {
    const md = `## EPIC-001 — Feature
### Definition of Done
- [ ] Item 1
- [ ] Item 2

### Description
Goal.
`;
    const doc = parseEpicMarkdown(md);
    const dodSection = doc.epics[0].sections.find(s => s.sectionKey === 'definition_of_done');
    
    // Remove all items
    expect(dodSection?.items).toBeDefined();
    if (dodSection && dodSection.items) {
      dodSection.items = [];
    }
    
    const result = serializeEpicMarkdown(doc);
    // Section heading should not appear
    expect(result).not.toContain('### Definition of Done');
    expect(result).toContain('### Description');
    expect(result).toContain('Goal.');
  });

  it('should remove section heading when all tasks are deleted from a tasklist section', () => {
    const md = `## EPIC-001 — Feature
### Tasks
- [ ] TASK-001 — Task 1
- [ ] TASK-002 — Task 2

### Description
Goal.
`;
    const doc = parseEpicMarkdown(md);
    const tasksSection = doc.epics[0].sections.find(s => s.type === 'tasklist');
    
    // Remove all tasks
    expect(tasksSection?.tasks).toBeDefined();
    if (tasksSection && tasksSection.tasks) {
      tasksSection.tasks = [];
    }
    
    const result = serializeEpicMarkdown(doc);
    // Section heading should not appear
    expect(result).not.toContain('### Tasks');
    expect(result).toContain('### Description');
    expect(result).toContain('Goal.');
  });

  it('should preserve depends_on position at end of EPIC after modifications', () => {
    const md = `## EPIC-001 — Feature
### Description
Goal.

depends_on: [EPIC-000]
`;
    const doc = parseEpicMarkdown(md);
    const epic = doc.epics[0];
    
    // Add a new section
    epic.sections.push({
      heading: 'Acceptance Criteria',
      headingLevel: 3,
      sectionKey: 'acceptance_criteria',
      type: 'checklist',
      content: '',
      items: [{ text: 'AC 1', checked: false, rawLine: '- [ ] AC 1', prefix: '- [ ] ' }],
      rawLines: [],
      preamble: ['### Acceptance Criteria'],
      postamble: [],
    });
    
    const result = serializeEpicMarkdown(doc);
    
    // depends_on should be at the end
    const lastDependsOnIndex = result.lastIndexOf('depends_on:');
    const lastSectionIndex = Math.max(
      result.lastIndexOf('### Acceptance Criteria'),
      result.lastIndexOf('### Description')
    );
    
    expect(lastDependsOnIndex).toBeGreaterThan(lastSectionIndex);
    expect(result).toContain('depends_on: [EPIC-000]');
  });
});
