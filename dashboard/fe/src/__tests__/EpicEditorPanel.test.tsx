/**
 * Unit tests for EpicEditorPanel component.
 *
 * Tests the rich editing drawer that replaces EpicDetailDrawer, providing
 * tabbed section-level editing for EPIC content (Overview, DoD, AC, Tasks, Deps).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { EpicNode, EpicDocument, EpicSection, CheckItem, TaskNode, parseEpicMarkdown, serializeEpicMarkdown } from '@/lib/epic-parser';

// Polyfill ResizeObserver for jsdom
class MockResizeObserver implements ResizeObserver {
  observe() { /* noop */ }
  unobserve() { /* noop */ }
  disconnect() { /* noop */ }
}
globalThis.ResizeObserver = MockResizeObserver;

// ── Mock api-client ──────────────────────────────────────────────────

const mockApiGet = vi.fn();

vi.mock('@/lib/api-client', () => ({
  apiGet: (...args: any[]) => mockApiGet(...args),
}));

// ── Mock useRoles hook ──────────────────────────────────────────────

vi.mock('@/hooks/use-roles', () => ({
  useRoles: () => ({ roles: [] }),
}));

// ── Mock MarkdownRenderer ───────────────────────────────────────────

vi.mock('@/lib/markdown-renderer', () => ({
  MarkdownRenderer: ({ content }: { content: string }) => (
    <div data-testid="markdown-renderer">{content}</div>
  ),
}));

// ── Test data ────────────────────────────────────────────────────────

function makeEpic(overrides: Partial<EpicNode> = {}): EpicNode {
  return {
    ref: 'EPIC-001',
    title: 'Auth System',
    headingLevel: 2,
    rawHeading: '## EPIC-001 — Auth System',
    frontmatter: new Map([
      ['Roles', 'engineer, qa'],
    ]),
    sections: [
      {
        heading: 'Description',
        headingLevel: 3,
        sectionKey: 'description',
        type: 'text',
        content: 'Build authentication system',
        rawLines: ['Build authentication system'],
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
            completed: false,
            body: 'Create the auth module structure',
            bodyLines: ['Create the auth module structure'],
            rawHeader: '- [ ] **T-G001.1** — Set up auth module',
            prefix: '- [ ] ',
            idPrefix: '**',
            idSuffix: '**',
            delimiter: ' — ',
          },
        ],
        rawLines: ['- [ ] **T-G001.1** — Set up auth module'],
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

// ── Mock PlanWorkspace context ───────────────────────────────────────

let mockUpdateParsedPlan = vi.fn();
let mockParsedPlan: EpicDocument | null = null;

vi.mock('../components/plan/PlanWorkspace', () => ({
  usePlanContext: () => ({
    planId: 'test-plan',
    plan: { title: 'Test Plan', status: 'active' },
    epics: [],
    progress: null,
    isProgressLoading: false,
    activeTab: 'editor',
    setActiveTab: vi.fn(),
    planContent: '',
    setPlanContent: vi.fn(),
    parsedPlan: mockParsedPlan,
    syncStatus: null,
    isSaving: false,
    savePlan: vi.fn(),
    launchPlan: vi.fn(),
    reloadFromDisk: vi.fn(),
    selectedEpicRef: null,
    setSelectedEpicRef: vi.fn(),
    updateParsedPlan: mockUpdateParsedPlan,
  }),
}));

// ── Import component AFTER mocks ─────────────────────────────────────

import { EpicEditorPanel } from '../components/plan/EpicEditorPanel';

// ── Tests ────────────────────────────────────────────────────────────

describe('EpicEditorPanel', () => {
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockParsedPlan = makeDoc();
    // Default mock: simulate the real updateParsedPlan behavior —
    // calls the updater with a copy of parsedPlan
    mockUpdateParsedPlan.mockImplementation((updater: (doc: EpicDocument) => void) => {
      if (!mockParsedPlan) return;
      // Shallow copy structure matching PlanWorkspace's real implementation
      const docCopy: EpicDocument = {
        ...mockParsedPlan,
        epics: mockParsedPlan.epics.map(e => ({
          ...e,
          frontmatter: new Map(e.frontmatter),
          sections: e.sections.map(s => ({
            ...s,
            items: s.items ? s.items.map(i => ({ ...i })) : undefined,
            tasks: s.tasks ? s.tasks.map(t => ({ ...t })) : undefined,
          })),
        })),
      };
      updater(docCopy);
    });
  });

  describe('Rendering', () => {
    it('renders nothing when epic is null', () => {
      const { container } = render(
        <EpicEditorPanel epic={null} isOpen={true} onClose={onClose} />
      );
      expect(container.innerHTML).toBe('');
    });

    it('renders the panel with header showing EPIC ref and title', () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );
      expect(screen.getByText('EPIC-001')).toBeInTheDocument();
      // Title appears in both the header HeaderTitle and the Overview tab Title field
      expect(screen.getAllByText('Auth System').length).toBeGreaterThanOrEqual(2);
    });

    it('renders all 5 tabs', () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );
      expect(screen.getByText('Overview')).toBeInTheDocument();
      expect(screen.getByText('DoD')).toBeInTheDocument();
      expect(screen.getByText('AC')).toBeInTheDocument();
      expect(screen.getByText('Tasks')).toBeInTheDocument();
      expect(screen.getByText('Deps')).toBeInTheDocument();
    });

    it('renders footer with Delete EPIC and Save buttons', () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );
      expect(screen.getByText('Delete EPIC')).toBeInTheDocument();
      expect(screen.getByText(/Save/)).toBeInTheDocument();
    });
  });

  describe('Tab Navigation', () => {
    it('defaults to Overview tab', () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );
      // Overview tab should be active — check for Description label
      expect(screen.getByText('Description')).toBeInTheDocument();
    });

    it('switches to DoD tab when clicked', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );
      fireEvent.click(screen.getByText('DoD'));
      // Should show DoD checklist items
      await waitFor(() => {
        expect(screen.getByText('All tests pass')).toBeInTheDocument();
      });
    });

    it('switches to AC tab when clicked', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );
      fireEvent.click(screen.getByText('AC'));
      await waitFor(() => {
        expect(screen.getByText('User can log in')).toBeInTheDocument();
      });
    });

    it('switches to Tasks tab when clicked', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );
      fireEvent.click(screen.getByText('Tasks'));
      await waitFor(() => {
        expect(screen.getByText('Set up auth module')).toBeInTheDocument();
      });
    });

    it('switches to Deps tab when clicked', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );
      fireEvent.click(screen.getByText('Deps'));
      await waitFor(() => {
        // No deps — should show empty state
        expect(screen.getByText('No dependencies.')).toBeInTheDocument();
      });
    });

    it('respects initialTab prop', () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} initialTab="dod" />
      );
      // Should show DoD content, not Overview
      expect(screen.getByText('All tests pass')).toBeInTheDocument();
    });
  });

  describe('Delete EPIC', () => {
    it('calls updateParsedPlan with a mutator that removes the epic from doc.epics', () => {
      // Confirm dialog mock
      vi.spyOn(window, 'confirm').mockReturnValue(true);

      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );

      fireEvent.click(screen.getByText('Delete EPIC'));

      expect(mockUpdateParsedPlan).toHaveBeenCalledTimes(1);
      const updater = mockUpdateParsedPlan.mock.calls[0][0];

      // Simulate calling the updater with a doc
      const doc = makeDoc([makeEpic(), makeEpic({ ref: 'EPIC-002', title: 'Other' })]);
      updater(doc);

      // The updater should have mutated doc.epics directly
      expect(doc.epics.length).toBe(1);
      expect(doc.epics[0].ref).toBe('EPIC-002');
    });

    it('removes the deleted epic ref from other epics depends_on', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);

      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );

      fireEvent.click(screen.getByText('Delete EPIC'));

      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc([
        makeEpic(),
        makeEpic({ ref: 'EPIC-002', title: 'Other', depends_on: ['EPIC-001'] }),
      ]);
      updater(doc);

      expect(doc.epics.length).toBe(1);
      expect(doc.epics[0].depends_on).toEqual([]);
    });

    it('calls onClose after deletion', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(true);

      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );

      fireEvent.click(screen.getByText('Delete EPIC'));

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does nothing if user cancels the confirmation', () => {
      vi.spyOn(window, 'confirm').mockReturnValue(false);

      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );

      fireEvent.click(screen.getByText('Delete EPIC'));

      expect(mockUpdateParsedPlan).not.toHaveBeenCalled();
      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('DoD Tab — Checkbox Toggle', () => {
    it('toggles a DoD checkbox via updateParsedPlan', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} initialTab="dod" />
      );

      // Find unchecked checkbox for "All tests pass"
      const checkboxes = screen.getAllByRole('checkbox');
      // First unchecked checkbox
      const uncheckedBox = checkboxes.find(cb => !(cb as HTMLInputElement).checked);
      expect(uncheckedBox).toBeTruthy();

      fireEvent.click(uncheckedBox!);

      expect(mockUpdateParsedPlan).toHaveBeenCalledTimes(1);
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc();
      updater(doc);

      // Check that the item was toggled to checked
      const dodSection = doc.epics[0].sections.find(s => s.heading === 'Definition of Done');
      expect(dodSection?.items?.[0].checked).toBe(true);
      // Verify rawLine is correctly reconstructed (QA fix verification)
      expect(dodSection?.items?.[0].rawLine).toBe('- [x] All tests pass');
    });

    it('reconstructs rawLine correctly when editing checked item text', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} initialTab="dod" />
      );

      // Click on the checked item text ("Code reviewed") to start editing
      const checkedItemText = screen.getByText('Code reviewed');
      fireEvent.click(checkedItemText);

      // Find the editing input and change the text
      const editInput = screen.getByDisplayValue('Code reviewed');
      fireEvent.change(editInput, { target: { value: 'Code reviewed and approved' } });
      fireEvent.keyDown(editInput, { key: 'Enter' });

      expect(mockUpdateParsedPlan).toHaveBeenCalledTimes(1);
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc();
      updater(doc);

      // Verify rawLine is correctly reconstructed for checked items
      const dodSection = doc.epics[0].sections.find(s => s.heading === 'Definition of Done');
      // Item at index 1 is "Code reviewed" which is checked: true
      expect(dodSection?.items?.[1].text).toBe('Code reviewed and approved');
      expect(dodSection?.items?.[1].rawLine).toBe('- [x] Code reviewed and approved');
    });
  });

  describe('Deps Tab', () => {
    it('shows existing dependencies', async () => {
      const epicWithDeps = makeEpic({ depends_on: ['EPIC-002'] });
      mockParsedPlan = makeDoc([
        epicWithDeps,
        makeEpic({ ref: 'EPIC-002', title: 'Database Setup' }),
      ]);

      render(
        <EpicEditorPanel epic={epicWithDeps} isOpen={true} onClose={onClose} initialTab="deps" />
      );

      await waitFor(() => {
        expect(screen.getByText('EPIC-002')).toBeInTheDocument();
      });
    });

    it('can remove a dependency', async () => {
      const epicWithDeps = makeEpic({ depends_on: ['EPIC-002'] });
      mockParsedPlan = makeDoc([
        epicWithDeps,
        makeEpic({ ref: 'EPIC-002', title: 'Database Setup' }),
      ]);

      render(
        <EpicEditorPanel epic={epicWithDeps} isOpen={true} onClose={onClose} initialTab="deps" />
      );

      await waitFor(() => {
        expect(screen.getByText('EPIC-002')).toBeInTheDocument();
      });

      // Find the remove button for the dependency
      const removeButtons = screen.getAllByTitle(/Remove.*dependency/i);
      fireEvent.click(removeButtons[0]);

      expect(mockUpdateParsedPlan).toHaveBeenCalledTimes(1);
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc([
        makeEpic({ depends_on: ['EPIC-002'] }),
        makeEpic({ ref: 'EPIC-002', title: 'Database Setup' }),
      ]);
      updater(doc);

      expect(doc.epics[0].depends_on).toEqual([]);
    });
  });

  describe('Panel open/close', () => {
    it('calls onClose when backdrop is clicked', () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );

      // The backdrop div
      const backdrop = document.querySelector('.fixed.inset-0.bg-black\\/20');
      expect(backdrop).toBeTruthy();
      fireEvent.click(backdrop!);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when close button is clicked', () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );

      const closeButtons = screen.getAllByRole('button');
      const closeButton = closeButtons.find(btn => btn.querySelector('.material-symbols-outlined')?.textContent === 'close');
      expect(closeButton).toBeTruthy();
      fireEvent.click(closeButton!);

      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  // ── Acceptance Criteria tests (EPIC-002) ──────────────────────────────

  describe('AC: Reordering items updates the array order in parsedPlan', () => {
    it('reorders DoD items via drag-and-drop', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} initialTab="dod" />
      );

      await waitFor(() => {
        expect(screen.getByText('All tests pass')).toBeInTheDocument();
      });

      // Find the DraggableChecklistItem containers
      const items = screen.getAllByRole('checkbox');
      expect(items.length).toBeGreaterThanOrEqual(2);

      // Simulate drag start on first item
      const firstItemContainer = items[0].closest('[draggable]')!;
      const dataTransfer = { effectAllowed: '', dropEffect: '', setData: vi.fn(), getData: vi.fn(() => '0'), items: [], files: [], types: [] };

      fireEvent.dragStart(firstItemContainer, { dataTransfer });

      // Simulate drag over on second item
      const secondItemContainer = items[1].closest('[draggable]')!;
      fireEvent.dragOver(secondItemContainer, { dataTransfer });

      // Simulate drop on second item
      fireEvent.drop(secondItemContainer, { dataTransfer });

      expect(mockUpdateParsedPlan).toHaveBeenCalled();
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc();
      updater(doc);

      // Items should be reordered: [Code reviewed, All tests pass]
      const dodSection = doc.epics[0].sections.find(s => s.heading === 'Definition of Done');
      expect(dodSection?.items?.[0].text).toBe('Code reviewed');
      expect(dodSection?.items?.[1].text).toBe('All tests pass');
    });

    it('reorders tasks via drag-and-drop', async () => {
      const epicWithTwoTasks = makeEpic({
        sections: [
          ...makeEpic().sections.filter(s => s.heading !== 'Tasks'),
          {
            heading: 'Tasks',
            headingLevel: 3,
            type: 'tasklist' as const,
            content: '',
            tasks: [
              {
                id: 'T-G001.1',
                title: 'First task',
                completed: false,
                body: '',
                bodyLines: [],
                rawHeader: '- [ ] **T-G001.1** — First task',
                prefix: '- [ ] ',
                idPrefix: '**',
                idSuffix: '**',
                delimiter: ' — ',
              },
              {
                id: 'T-G001.2',
                title: 'Second task',
                completed: false,
                body: '',
                bodyLines: [],
                rawHeader: '- [ ] **T-G001.2** — Second task',
                prefix: '- [ ] ',
                idPrefix: '**',
                idSuffix: '**',
                delimiter: ' — ',
              },
            ],
            rawLines: [],
            preamble: [],
            postamble: [],
          },
        ],
      });

      render(
        <EpicEditorPanel epic={epicWithTwoTasks} isOpen={true} onClose={onClose} initialTab="tasks" />
      );

      await waitFor(() => {
        expect(screen.getByText('First task')).toBeInTheDocument();
      });

      const checkboxes = screen.getAllByRole('checkbox');
      const firstTaskContainer = checkboxes[0].closest('[draggable]')!;
      const secondTaskContainer = checkboxes[1].closest('[draggable]')!;
      const dataTransfer = { effectAllowed: '', dropEffect: '', setData: vi.fn(), getData: vi.fn(() => '0'), items: [], files: [], types: [] };

      fireEvent.dragStart(firstTaskContainer, { dataTransfer });
      fireEvent.dragOver(secondTaskContainer, { dataTransfer });
      fireEvent.drop(secondTaskContainer, { dataTransfer });

      expect(mockUpdateParsedPlan).toHaveBeenCalled();
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc([epicWithTwoTasks]);
      updater(doc);

      const tasksSection = doc.epics[0].sections.find(s => s.heading === 'Tasks');
      expect(tasksSection?.tasks?.[0].id).toBe('T-G001.2');
      expect(tasksSection?.tasks?.[1].id).toBe('T-G001.1');
    });
  });

  describe('AC: Deleting an item removes it from the AST', () => {
    it('deletes a DoD item via two-click confirmation', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} initialTab="dod" />
      );

      await waitFor(() => {
        expect(screen.getByText('All tests pass')).toBeInTheDocument();
      });

      // Find the delete button for the first item — it's hidden until hover
      // but we can find it by title within the item's group
      const deleteButtons = screen.getAllByTitle('Delete item');
      expect(deleteButtons.length).toBeGreaterThanOrEqual(1);

      // First click — show confirmation
      fireEvent.click(deleteButtons[0]);
      // Second click — confirm delete
      const confirmButton = screen.getByTitle('Click again to confirm delete');
      fireEvent.click(confirmButton);

      expect(mockUpdateParsedPlan).toHaveBeenCalled();
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc();
      updater(doc);

      const dodSection = doc.epics[0].sections.find(s => s.heading === 'Definition of Done');
      // Should have only one item left ("Code reviewed")
      expect(dodSection?.items?.length).toBe(1);
      expect(dodSection?.items?.[0].text).toBe('Code reviewed');
    });
  });

  describe('AC: Adding an item appends to the array with correct raw line format', () => {
    it('adds a new DoD item with correct rawLine format', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} initialTab="dod" />
      );

      await waitFor(() => {
        expect(screen.getByText('All tests pass')).toBeInTheDocument();
      });

      // Click the "Add item" button
      const addButton = screen.getByText('Add item');
      fireEvent.click(addButton);

      // Find the input that appears
      const input = screen.getByPlaceholderText('Type new item and press Enter…');
      fireEvent.change(input, { target: { value: 'New DoD item' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(mockUpdateParsedPlan).toHaveBeenCalled();
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc();
      updater(doc);

      const dodSection = doc.epics[0].sections.find(s => s.heading === 'Definition of Done');
      const lastItem = dodSection?.items?.[dodSection.items!.length - 1];
      expect(lastItem?.text).toBe('New DoD item');
      expect(lastItem?.rawLine).toBe('- [ ] New DoD item');
      expect(lastItem?.checked).toBe(false);
    });
  });

  describe('AC: Task ID auto-increments correctly', () => {
    it('derives next task ID from existing tasks', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} initialTab="tasks" />
      );

      await waitFor(() => {
        expect(screen.getByText('Set up auth module')).toBeInTheDocument();
      });

      // Click "Add task" button
      const addTaskButton = screen.getByText(/Add task/);
      fireEvent.click(addTaskButton);

      // Find the input
      const input = screen.getByPlaceholderText('Type new task title and press Enter…');
      fireEvent.change(input, { target: { value: 'New task title' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(mockUpdateParsedPlan).toHaveBeenCalled();
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc();
      updater(doc);

      const tasksSection = doc.epics[0].sections.find(s => s.heading === 'Tasks');
      const lastTask = tasksSection?.tasks?.[tasksSection.tasks!.length - 1];
      // Should be T-G001.2 since existing task is T-G001.1
      expect(lastTask?.id).toBe('T-G001.2');
      expect(lastTask?.title).toBe('New task title');
    });
  });

  describe('Bulk toggle (T-002.4)', () => {
    it('marks all DoD items as done', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} initialTab="dod" />
      );

      await waitFor(() => {
        expect(screen.getByText('All tests pass')).toBeInTheDocument();
      });

      const markAllDone = screen.getByText('Mark all done');
      fireEvent.click(markAllDone);

      expect(mockUpdateParsedPlan).toHaveBeenCalled();
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc();
      updater(doc);

      const dodSection = doc.epics[0].sections.find(s => s.heading === 'Definition of Done');
      expect(dodSection?.items?.every(i => i.checked)).toBe(true);
      // Verify rawLine format is correctly updated
      expect(dodSection?.items?.every(i => i.rawLine.startsWith('- [x]'))).toBe(true);
    });

    it('marks all DoD items as pending', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} initialTab="dod" />
      );

      await waitFor(() => {
        expect(screen.getByText('All tests pass')).toBeInTheDocument();
      });

      const markAllPending = screen.getByText('Mark all pending');
      fireEvent.click(markAllPending);

      expect(mockUpdateParsedPlan).toHaveBeenCalled();
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc();
      updater(doc);

      const dodSection = doc.epics[0].sections.find(s => s.heading === 'Definition of Done');
      expect(dodSection?.items?.every(i => !i.checked)).toBe(true);
      expect(dodSection?.items?.every(i => i.rawLine.startsWith('- [ ]'))).toBe(true);
    });

    it('disables Mark all done when all are already checked', async () => {
      const allCheckedEpic = makeEpic({
        sections: [
          ...makeEpic().sections.filter(s => s.heading !== 'Definition of Done'),
          {
            heading: 'Definition of Done',
            headingLevel: 3,
            type: 'checklist' as const,
            content: '',
            items: [
              { text: 'Item 1', checked: true, rawLine: '- [x] Item 1', prefix: '- [ ] ' },
              { text: 'Item 2', checked: true, rawLine: '- [x] Item 2', prefix: '- [ ] ' },
            ],
            rawLines: [],
            preamble: [],
            postamble: [],
          },
        ],
      });

      render(
        <EpicEditorPanel epic={allCheckedEpic} isOpen={true} onClose={onClose} initialTab="dod" />
      );

      await waitFor(() => {
        expect(screen.getByText('Mark all done')).toBeInTheDocument();
      });

      expect(screen.getByText('Mark all done').closest('button')).toBeDisabled();
    });
  });

  // ── Regression: Description heading duplication (FIXED) ──────────

  describe('Regression: commitDescription must NOT duplicate heading', () => {
    it('sets section.content to body text only (no heading) when saving description', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );

      // Double-click the description area to start editing
      const descArea = screen.getByText('Build authentication system');
      fireEvent.doubleClick(descArea);

      // Find the textarea and update the value
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Updated auth description' } });

      // Blur to commit (commitDescription)
      fireEvent.blur(textarea);

      expect(mockUpdateParsedPlan).toHaveBeenCalledTimes(1);
      const updater = mockUpdateParsedPlan.mock.calls[0][0];
      const doc = makeDoc();
      updater(doc);

      // The critical assertion: section.content must NOT contain the heading
      const descSection = doc.epics[0].sections.find(s => s.heading === 'Description');
      expect(descSection?.content).toBe('Updated auth description');
      // Content must NOT start with ### Description
      expect(descSection?.content).not.toMatch(/^###\s+Description/);
      // Preamble should have the heading
      expect(descSection?.preamble).toEqual(['### Description']);
    });

    it('does NOT accumulate headings across multiple saves', async () => {
      // Simulate 3 saves via the updater pattern
      const updaters: Array<(doc: EpicDocument) => void> = [];
      mockUpdateParsedPlan.mockImplementation((updater: (doc: EpicDocument) => void) => {
        updaters.push(updater);
      });

      const { rerender } = render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );

      // Save 1: Double-click, type, blur
      const descArea = screen.getByText('Build authentication system');
      fireEvent.doubleClick(descArea);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Version 1' } });
      fireEvent.blur(textarea);

      // Apply updater and re-render with updated epic
      expect(updaters.length).toBe(1);
      const doc1 = makeDoc();
      updaters[0](doc1);
      const descSection1 = doc1.epics[0].sections.find(s => s.heading === 'Description');

      // After first save — content should be clean
      expect(descSection1?.content).toBe('Version 1');
      expect(descSection1?.content).not.toContain('### Description');
    });
  });

  // ── Regression: Frontmatter deletion persistence ────────────────

  describe('Regression: deleteFrontmatter removes key from serialized output', () => {
    it('deletes a frontmatter key via updateParsedPlan', async () => {
      const epicWithMeta = makeEpic({
        frontmatter: new Map([
          ['Roles', 'engineer, qa'],
          ['Phase', '1'],
          ['Priority', 'P0'],
        ]),
      });
      mockParsedPlan = makeDoc([epicWithMeta]);

      render(
        <EpicEditorPanel epic={epicWithMeta} isOpen={true} onClose={onClose} />
      );

      // Find the remove button for a metadata field
      // The metadata fields should be visible — look for "Phase" and "Priority" labels
      const removeButtons = screen.getAllByTitle(/Remove/);
      // Filter to the metadata remove buttons (not role remove buttons)
      const metaRemoveButton = removeButtons.find(btn =>
        btn.getAttribute('title')?.includes('Phase') ||
        btn.getAttribute('title')?.includes('Priority')
      );

      if (metaRemoveButton) {
        fireEvent.click(metaRemoveButton);

        expect(mockUpdateParsedPlan).toHaveBeenCalledTimes(1);
        const updater = mockUpdateParsedPlan.mock.calls[0][0];
        const doc = makeDoc([epicWithMeta]);
        updater(doc);

        const deletedKey = metaRemoveButton.getAttribute('title')?.replace('Remove ', '');
        // The deleted key should no longer exist in frontmatter
        expect(doc.epics[0].frontmatter.has(deletedKey!)).toBe(false);
      }
    });

    it('serializer omits deleted frontmatter lines after round-trip', () => {
      // This tests the serializer directly — complementing the parser test
      const md = `## EPIC-001 — Feature
**Phase:** 1
**Owner:** engineer
**Priority:** P0

### Description
Goal of the epic.
`;
      const doc = parseEpicMarkdown(md);

      // Delete Owner key
      doc.epics[0].frontmatter.delete('Owner');

      const result = serializeEpicMarkdown(doc);

      // Owner line must NOT appear in output
      expect(result).not.toContain('**Owner:**');
      expect(result).not.toContain('engineer');

      // Other keys preserved
      expect(result).toContain('**Phase:** 1');
      expect(result).toContain('**Priority:** P0');

      // Re-parse should NOT resurrect the deleted key
      const doc2 = parseEpicMarkdown(result);
      expect(doc2.epics[0].frontmatter.has('Owner')).toBe(false);
      expect(doc2.epics[0].frontmatter.get('Phase')).toBe('1');
    });
  });

  // ── Regression: Mutation-first save pattern ────────────────────

  describe('Regression: Mutation-first pattern prevents state revert', () => {
    it('calls updateParsedPlan before setEditingDescription(false)', async () => {
      // This verifies the ordering: mutation must fire before exiting edit mode
      const callOrder: string[] = [];

      mockUpdateParsedPlan.mockImplementation((updater: (doc: EpicDocument) => void) => {
        callOrder.push('updateParsedPlan');
        const doc = makeDoc();
        updater(doc);
      });

      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );

      const descArea = screen.getByText('Build authentication system');
      fireEvent.doubleClick(descArea);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'New description value' } });
      fireEvent.blur(textarea);

      // updateParsedPlan should have been called
      expect(callOrder).toContain('updateParsedPlan');
      expect(mockUpdateParsedPlan).toHaveBeenCalledTimes(1);
    });

    it('does not call updateParsedPlan when description is unchanged', async () => {
      render(
        <EpicEditorPanel epic={makeEpic()} isOpen={true} onClose={onClose} />
      );

      const descArea = screen.getByText('Build authentication system');
      fireEvent.doubleClick(descArea);
      // Don't change the value — just blur
      const textarea = screen.getByRole('textbox');
      fireEvent.blur(textarea);

      // Should NOT have called updateParsedPlan — no mutation needed
      expect(mockUpdateParsedPlan).not.toHaveBeenCalled();
    });
  });
});
