import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EpicCardPreview } from '../components/plan/EpicCardPreview';
import { EpicNode } from '../lib/epic-parser';

vi.mock('../components/plan/PlanWorkspace', () => ({
  usePlanContext: () => ({
    updateParsedPlan: mockUpdateParsedPlan,
  }),
}));

vi.mock('../hooks/use-roles', () => ({
  useRoles: () => ({
    roles: [
      { name: 'engineer', description: 'Software engineer' },
      { name: 'qa', description: 'Quality assurance' },
    ],
  }),
}));

const mockUpdateParsedPlan = vi.fn();

const createMockEpic = (): EpicNode => ({
  ref: 'EPIC-001',
  title: 'Test Feature',
  headingLevel: 2,
  rawHeading: '## EPIC-001 — Test Feature',
  frontmatter: new Map([
    ['Phase', '1'],
    ['Owner', 'engineer'],
  ]),
  sections: [
    {
      heading: 'Description',
      headingLevel: 3,
      sectionKey: 'description',
      type: 'text',
      content: 'This is a test feature description.',
      rawLines: ['### Description', 'This is a test feature description.'],
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
        { text: 'Feature implemented', checked: false, rawLine: '- [ ] Feature implemented', prefix: '- [ ] ' },
        { text: 'Tests written', checked: true, rawLine: '- [x] Tests written', prefix: '- [x] ' },
      ],
      rawLines: ['### Definition of Done', '- [ ] Feature implemented', '- [x] Tests written'],
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
          id: 'T-001.1',
          title: 'First task',
          completed: false,
          body: '',
          bodyLines: [],
          rawHeader: '- [ ] **T-001.1** — First task',
          prefix: '- [ ] ',
          idPrefix: '**',
          idSuffix: '**',
          delimiter: ' — ',
        },
        {
          id: 'T-001.2',
          title: 'Second task',
          completed: true,
          body: 'Acceptance Criteria:\n- Criteria met',
          bodyLines: ['Acceptance Criteria:', '- Criteria met'],
          rawHeader: '- [x] **T-001.2** — Second task',
          prefix: '- [x] ',
          idPrefix: '**',
          idSuffix: '**',
          delimiter: ' — ',
        },
      ],
      rawLines: ['### Tasks', '- [ ] **T-001.1** — First task'],
      preamble: [],
      postamble: [],
    },
  ],
  depends_on: [],
  rawDependsOn: '',
});

describe('EpicCardPreview', () => {
  let mockEpic: EpicNode;

  beforeEach(() => {
    vi.clearAllMocks();
    mockEpic = createMockEpic();
  });

  it('renders EPIC reference badge', () => {
    render(<EpicCardPreview epic={mockEpic} />);
    expect(screen.getByText('EPIC-001')).toBeInTheDocument();
  });

  it('renders EPIC title', () => {
    render(<EpicCardPreview epic={mockEpic} />);
    expect(screen.getByText('Test Feature')).toBeInTheDocument();
  });

  it('renders Description section', () => {
    render(<EpicCardPreview epic={mockEpic} />);
    expect(screen.getByText('Description')).toBeInTheDocument();
    expect(screen.getByText('This is a test feature description.')).toBeInTheDocument();
  });

  it('renders Definition of Done section', () => {
    render(<EpicCardPreview epic={mockEpic} />);
    expect(screen.getByText(/Definition of Done/i)).toBeInTheDocument();
  });

  it('renders DoD checklist items', () => {
    render(<EpicCardPreview epic={mockEpic} />);
    expect(screen.getByText('Feature implemented')).toBeInTheDocument();
    expect(screen.getByText('Tests written')).toBeInTheDocument();
  });

  it('renders Tasks section', () => {
    render(<EpicCardPreview epic={mockEpic} />);
    expect(screen.getByText(/Tasks/i)).toBeInTheDocument();
  });

  it('renders task items with IDs', () => {
    render(<EpicCardPreview epic={mockEpic} />);
    expect(screen.getByText('T-001.1')).toBeInTheDocument();
    expect(screen.getByText('T-001.2')).toBeInTheDocument();
  });

  it('renders task titles', () => {
    render(<EpicCardPreview epic={mockEpic} />);
    expect(screen.getByText('First task')).toBeInTheDocument();
    expect(screen.getByText('Second task')).toBeInTheDocument();
  });

  it('shows frontmatter badges', () => {
    render(<EpicCardPreview epic={mockEpic} />);
    expect(screen.getByText('Phase')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('shows Roles section', () => {
    render(<EpicCardPreview epic={mockEpic} />);
    expect(screen.getByText('Roles')).toBeInTheDocument();
    expect(screen.getByText('engineer')).toBeInTheDocument();
  });

  describe('DoD checkbox interaction', () => {
    it('toggles checklist item on click', () => {
      render(<EpicCardPreview epic={mockEpic} />);
      const checkboxes = screen.getAllByRole('checkbox');
      const firstDoDCheckbox = checkboxes[0];
      fireEvent.click(firstDoDCheckbox);
      expect(mockUpdateParsedPlan).toHaveBeenCalled();
    });
  });

  describe('Task checkbox interaction', () => {
    it('toggles task on click', () => {
      render(<EpicCardPreview epic={mockEpic} />);
      const checkboxes = screen.getAllByRole('checkbox');
      const taskCheckboxes = checkboxes.filter((cb) => cb.closest('[class*="rounded-lg"]'));
      if (taskCheckboxes.length > 0) {
        fireEvent.click(taskCheckboxes[0]);
        expect(mockUpdateParsedPlan).toHaveBeenCalled();
      }
    });
  });

  describe('Title editing', () => {
    it('enters edit mode on double-click', async () => {
      render(<EpicCardPreview epic={mockEpic} />);
      const title = screen.getByText('Test Feature');
      fireEvent.dblClick(title);
      await waitFor(() => {
        expect(screen.getByDisplayValue('Test Feature')).toBeInTheDocument();
      });
    });
  });

  describe('Add item functionality', () => {
    it('shows add item button for checklist sections', () => {
      render(<EpicCardPreview epic={mockEpic} />);
      const addButtons = screen.getAllByRole('button', { name: /add item/i });
      expect(addButtons.length).toBeGreaterThan(0);
    });

    it('shows add task button for task sections', () => {
      render(<EpicCardPreview epic={mockEpic} />);
      const addTaskButtons = screen.getAllByRole('button', { name: /add task/i });
      expect(addTaskButtons.length).toBeGreaterThan(0);
    });
  });

  describe('EPIC with dependencies', () => {
    it('shows dependencies when present', () => {
      mockEpic.depends_on = ['EPIC-000'];
      render(<EpicCardPreview epic={mockEpic} />);
      expect(screen.getByText(/Depends on/i)).toBeInTheDocument();
      expect(screen.getByText('EPIC-000')).toBeInTheDocument();
    });
  });

  describe('EPIC without dependencies', () => {
    it('does not show dependencies section', () => {
      render(<EpicCardPreview epic={mockEpic} />);
      expect(screen.queryByText(/Depends on/i)).not.toBeInTheDocument();
    });
  });
});
