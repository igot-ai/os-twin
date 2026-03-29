import { describe, it, expect } from 'vitest';
import { deriveDAGFromDocument, wouldCreateCycle } from './dag-layout';
import { EpicDocument } from './epic-parser';

describe('DAG Layout logic', () => {
  it('should derive a correct DAG structure from an EpicDocument', () => {
    const doc: EpicDocument = {
      title: '# Plan',
      preamble: '',
      epics: [
        {
          ref: 'EPIC-001',
          title: 'A',
          headingLevel: 2,
          rawHeading: '## EPIC-001 — A',
          frontmatter: new Map(),
          sections: [],
          depends_on: [],
          rawDependsOn: ''
        },
        {
          ref: 'EPIC-002',
          title: 'B',
          headingLevel: 2,
          rawHeading: '## EPIC-002 — B',
          frontmatter: new Map(),
          sections: [],
          depends_on: ['EPIC-001'],
          rawDependsOn: ''
        }
      ],
      postamble: ''
    };
    
    const dag = deriveDAGFromDocument(doc);
    expect(dag.nodes['EPIC-001']).toBeDefined();
    expect(dag.nodes['EPIC-002']).toBeDefined();
    expect(dag.waves['0']).toContain('EPIC-001');
    expect(dag.waves['1']).toContain('EPIC-002');
  });

  it('should detect cycles correctly', () => {
    const doc: EpicDocument = {
      title: '# Plan',
      preamble: '',
      epics: [
        {
          ref: 'EPIC-001',
          title: 'A',
          headingLevel: 2,
          rawHeading: '## EPIC-001 — A',
          frontmatter: new Map(),
          sections: [],
          depends_on: [],
          rawDependsOn: ''
        },
        {
          ref: 'EPIC-002',
          title: 'B',
          headingLevel: 2,
          rawHeading: '## EPIC-002 — B',
          frontmatter: new Map(),
          sections: [],
          depends_on: ['EPIC-001'],
          rawDependsOn: ''
        }
      ],
      postamble: ''
    };
    
    // Adding 2 -> 1 creates a cycle because 1 -> 2 exists (depends_on is from source to target)
    // Wait, depends_on means target depends on source.
    // So 1 -> 2 means 2 depends on 1.
    // adding 2 to 1's depends_on would mean 1 depends on 2. 
    // Cycle: 1 -> 2 -> 1.
    
    expect(wouldCreateCycle(doc, 'EPIC-002', 'EPIC-001')).toBe(true);
    expect(wouldCreateCycle(doc, 'EPIC-001', 'EPIC-002')).toBe(false); // already exists
  });
});
