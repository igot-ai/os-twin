/**
 * Unit tests for computeEpicStats utility (EPIC-003).
 *
 * Tests the computation of per-EPIC progress stats from an EpicDocument,
 * including task/DoD counts, AC presence, and description extraction.
 */
import { describe, it, expect } from 'vitest';
import { computeEpicStats, EpicStats } from '../lib/epic-stats';
import { EpicDocument, EpicNode } from '../lib/epic-parser';

// ── Test data factories ─────────────────────────────────────────────

function makeEpic(overrides: Partial<EpicNode> = {}): EpicNode {
  return {
    ref: 'EPIC-001',
    title: 'Auth System',
    headingLevel: 2,
    rawHeading: '## EPIC-001 — Auth System',
    frontmatter: new Map([['Roles', 'engineer']]),
    sections: [
      {
        heading: 'Description',
        headingLevel: 3,
        sectionKey: 'description',
        type: 'text',
        content: 'Build the authentication system',
        rawLines: ['Build the authentication system'],
        preamble: [],
        postamble: [],
      },
      {
        heading: 'Definition of Done',
        headingLevel: 3,
        sectionKey: 'definition_of_done',
        type: 'checklist',
        content: '',
        items: [
          { text: 'All tests pass', checked: false, rawLine: '- [ ] All tests pass', prefix: '- [ ] ' },
          { text: 'Code reviewed', checked: true, rawLine: '- [x] Code reviewed', prefix: '- [ ] ' },
        ],
        rawLines: ['- [ ] All tests pass', '- [x] Code reviewed'],
        preamble: [],
        postamble: [],
      },
      {
        heading: 'Acceptance Criteria',
        headingLevel: 3,
        sectionKey: 'acceptance_criteria',
        type: 'checklist',
        content: '',
        items: [
          { text: 'User can log in', checked: false, rawLine: '- [ ] User can log in', prefix: '- [ ] ' },
        ],
        rawLines: ['- [ ] User can log in'],
        preamble: [],
        postamble: [],
      },
      {
        heading: 'Tasks',
        headingLevel: 3,
        sectionKey: 'tasks',
        type: 'tasklist',
        content: '',
        tasks: [
          {
            id: 'T-G001.1',
            title: 'Set up auth module',
            completed: true,
            body: '',
            bodyLines: [],
            rawHeader: '- [x] **T-G001.1** — Set up auth module',
            prefix: '- [ ] ',
            idPrefix: '**',
            idSuffix: '**',
            delimiter: ' — ',
          },
          {
            id: 'T-G001.2',
            title: 'Implement login',
            completed: false,
            body: '',
            bodyLines: [],
            rawHeader: '- [ ] **T-G001.2** — Implement login',
            prefix: '- [ ] ',
            idPrefix: '**',
            idSuffix: '**',
            delimiter: ' — ',
          },
          {
            id: 'T-G001.3',
            title: 'Write tests',
            completed: false,
            body: '',
            bodyLines: [],
            rawHeader: '- [ ] **T-G001.3** — Write tests',
            prefix: '- [ ] ',
            idPrefix: '**',
            idSuffix: '**',
            delimiter: ' — ',
          },
        ],
        rawLines: ['- [x] **T-G001.1** — Set up auth module', '- [ ] **T-G001.2** — Implement login', '- [ ] **T-G001.3** — Write tests'],
        preamble: [],
        postamble: [],
      },
    ],
    depends_on: [],
    rawDependsOn: '',
    ...overrides,
  };
}

function makeDoc(epics: EpicNode[] = [makeEpic()]): EpicDocument {
  return {
    title: 'PLAN: Test Plan',
    preamble: '',
    epics,
    postamble: '',
  };
}

// ── Tests ────────────────────────────────────────────────────────────

describe('computeEpicStats', () => {
  it('returns empty map for null parsedPlan', () => {
    const result = computeEpicStats(null);
    expect(result.size).toBe(0);
  });

  it('computes correct task stats', () => {
    const result = computeEpicStats(makeDoc());
    const stats = result.get('EPIC-001')!;
    expect(stats.tasksTotal).toBe(3);
    expect(stats.tasksDone).toBe(1);
  });

  it('computes correct DoD stats', () => {
    const result = computeEpicStats(makeDoc());
    const stats = result.get('EPIC-001')!;
    expect(stats.dodTotal).toBe(2);
    expect(stats.dodDone).toBe(1);
  });

  it('detects presence of AC items', () => {
    const result = computeEpicStats(makeDoc());
    const stats = result.get('EPIC-001')!;
    expect(stats.hasAC).toBe(true);
  });

  it('detects absence of AC items', () => {
    const epic = makeEpic({
      sections: [
        {
          heading: 'Description',
          headingLevel: 3,
          type: 'text',
          content: 'Some description',
          rawLines: ['Some description'],
          preamble: [],
          postamble: [],
        },
        {
          heading: 'Acceptance Criteria',
          headingLevel: 3,
          type: 'checklist',
          content: '',
          items: [], // Empty AC list
          rawLines: [],
          preamble: [],
          postamble: [],
        },
      ],
    });
    const result = computeEpicStats(makeDoc([epic]));
    const stats = result.get('EPIC-001')!;
    expect(stats.hasAC).toBe(false);
  });

  it('detects missing AC section entirely', () => {
    const epic = makeEpic({
      sections: [
        {
          heading: 'Description',
          headingLevel: 3,
          type: 'text',
          content: 'Some description',
          rawLines: ['Some description'],
          preamble: [],
          postamble: [],
        },
      ],
    });
    const result = computeEpicStats(makeDoc([epic]));
    const stats = result.get('EPIC-001')!;
    expect(stats.hasAC).toBe(false);
  });

  it('extracts description from text section', () => {
    const result = computeEpicStats(makeDoc());
    const stats = result.get('EPIC-001')!;
    expect(stats.description).toBe('Build the authentication system');
  });

  it('handles 0% completion', () => {
    const epic = makeEpic({
      sections: [
        {
          heading: 'Tasks',
          headingLevel: 3,
          type: 'tasklist',
          content: '',
          tasks: [
            { id: 'T-1', title: 'Task 1', completed: false, body: '', bodyLines: [], rawHeader: '', prefix: '- [ ] ', idPrefix: '', idSuffix: '', delimiter: ' — ' },
            { id: 'T-2', title: 'Task 2', completed: false, body: '', bodyLines: [], rawHeader: '', prefix: '- [ ] ', idPrefix: '', idSuffix: '', delimiter: ' — ' },
          ],
          rawLines: [],
          preamble: [],
          postamble: [],
        },
        {
          heading: 'Definition of Done',
          headingLevel: 3,
          type: 'checklist',
          content: '',
          items: [
            { text: 'DoD 1', checked: false, rawLine: '', prefix: '- [ ] ' },
          ],
          rawLines: [],
          preamble: [],
          postamble: [],
        },
      ],
    });
    const result = computeEpicStats(makeDoc([epic]));
    const stats = result.get('EPIC-001')!;
    expect(stats.tasksDone).toBe(0);
    expect(stats.tasksTotal).toBe(2);
    expect(stats.dodDone).toBe(0);
    expect(stats.dodTotal).toBe(1);
  });

  it('handles 100% completion', () => {
    const epic = makeEpic({
      sections: [
        {
          heading: 'Tasks',
          headingLevel: 3,
          type: 'tasklist',
          content: '',
          tasks: [
            { id: 'T-1', title: 'Task 1', completed: true, body: '', bodyLines: [], rawHeader: '', prefix: '- [ ] ', idPrefix: '', idSuffix: '', delimiter: ' — ' },
          ],
          rawLines: [],
          preamble: [],
          postamble: [],
        },
        {
          heading: 'Definition of Done',
          headingLevel: 3,
          type: 'checklist',
          content: '',
          items: [
            { text: 'DoD 1', checked: true, rawLine: '', prefix: '- [ ] ' },
          ],
          rawLines: [],
          preamble: [],
          postamble: [],
        },
      ],
    });
    const result = computeEpicStats(makeDoc([epic]));
    const stats = result.get('EPIC-001')!;
    expect(stats.tasksDone).toBe(1);
    expect(stats.tasksTotal).toBe(1);
    expect(stats.dodDone).toBe(1);
    expect(stats.dodTotal).toBe(1);
  });

  it('handles multiple epics', () => {
    const epic1 = makeEpic({ ref: 'EPIC-001' });
    const epic2 = makeEpic({
      ref: 'EPIC-002',
      sections: [
        {
          heading: 'Description',
          headingLevel: 3,
          type: 'text',
          content: 'Second epic',
          rawLines: ['Second epic'],
          preamble: [],
          postamble: [],
        },
      ],
    });
    const result = computeEpicStats(makeDoc([epic1, epic2]));
    expect(result.size).toBe(2);
    expect(result.get('EPIC-001')!.tasksTotal).toBe(3);
    expect(result.get('EPIC-002')!.tasksTotal).toBe(0);
    expect(result.get('EPIC-002')!.description).toBe('Second epic');
  });

  it('recognizes "DoD" as shorthand for Definition of Done', () => {
    const epic = makeEpic({
      ref: 'EPIC-003',
      sections: [
        {
          heading: 'DoD',
          headingLevel: 3,
          type: 'checklist',
          content: '',
          items: [
            { text: 'Test passes', checked: true, rawLine: '', prefix: '- [ ] ' },
          ],
          rawLines: [],
          preamble: [],
          postamble: [],
        },
      ],
    });
    const result = computeEpicStats(makeDoc([epic]));
    const stats = result.get('EPIC-003')!;
    expect(stats.dodTotal).toBe(1);
    expect(stats.dodDone).toBe(1);
  });

  it('handles epic with no sections', () => {
    const epic: EpicNode = {
      ref: 'EPIC-004',
      title: 'Empty Epic',
      headingLevel: 2,
      rawHeading: '## EPIC-004 — Empty Epic',
      frontmatter: new Map(),
      sections: [],
      depends_on: [],
      rawDependsOn: '',
    };
    const result = computeEpicStats(makeDoc([epic]));
    const stats = result.get('EPIC-004')!;
    expect(stats.tasksDone).toBe(0);
    expect(stats.tasksTotal).toBe(0);
    expect(stats.dodDone).toBe(0);
    expect(stats.dodTotal).toBe(0);
    expect(stats.hasAC).toBe(false);
    expect(stats.description).toBe('');
  });
});
