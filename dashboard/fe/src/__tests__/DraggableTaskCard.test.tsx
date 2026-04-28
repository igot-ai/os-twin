/**
 * Unit tests for DraggableTaskCard component.
 *
 * Tests the reusable task card component with drag handle, checkbox,
 * inline title editing, collapsible body editing, delete confirmation,
 * and keyboard support.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DraggableTaskCard } from '../components/plan/DraggableTaskCard';
import { TaskNode } from '@/lib/epic-parser';

// Polyfill ResizeObserver for jsdom
class MockResizeObserver implements ResizeObserver {
  observe() { /* noop */ }
  unobserve() { /* noop */ }
  disconnect() { /* noop */ }
}
globalThis.ResizeObserver = MockResizeObserver;

// Mock dataTransfer for jsdom (not available by default)
const mockDataTransfer = {
  effectAllowed: '',
  dropEffect: '',
  setData: vi.fn(),
  getData: vi.fn(() => ''),
  items: [],
  files: [],
  types: [],
};

// ── Mock MarkdownRenderer ─────────────────────────────────────────────

vi.mock('@/lib/markdown-renderer', () => ({
  MarkdownRenderer: ({ content }: { content: string }) => (
    <div data-testid="markdown-renderer">{content}</div>
  ),
}));

// ── Test data ────────────────────────────────────────────────────────

function makeTask(overrides: Partial<TaskNode> = {}): TaskNode {
  return {
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
    ...overrides,
  };
}

// ── Tests ────────────────────────────────────────────────────────────

describe('DraggableTaskCard', () => {
  const onToggle = vi.fn();
  const onEditTitle = vi.fn();
  const onEditBody = vi.fn();
  const onDelete = vi.fn();
  const onDragStart = vi.fn();
  const onDragEnd = vi.fn();
  const onDragOver = vi.fn();
  const onDrop = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const defaultProps = {
    index: 0,
    isDragOver: false,
    onToggle,
    onEditTitle,
    onEditBody,
    onDelete,
    onDragStart,
    onDragEnd,
    onDragOver,
    onDrop,
  };

  // ── Rendering ──────────────────────────────────────────────────────

  describe('Rendering', () => {
    it('renders the task title', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      expect(screen.getByText('Set up auth module')).toBeInTheDocument();
    });

    it('renders the task ID badge', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      expect(screen.getByText('T-G001.1')).toBeInTheDocument();
    });

    it('renders a checkbox with correct checked state', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ completed: true })} />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeChecked();
    });

    it('renders unchecked checkbox for incomplete task', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ completed: false })} />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).not.toBeChecked();
    });

    it('renders a drag handle with drag_indicator icon', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      expect(screen.getByText('drag_indicator')).toBeInTheDocument();
    });

    it('applies line-through style to completed task title', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ completed: true })} />);
      const titleSpan = screen.getByText('Set up auth module');
      expect(titleSpan.className).toContain('line-through');
    });

    it('shows "Show details" button when body exists', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ body: 'Some details' })} />);
      expect(screen.getByText('Show details')).toBeInTheDocument();
    });

    it('shows "Add details" button when no body exists', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ body: '', bodyLines: [] })} />);
      expect(screen.getByText('Add details')).toBeInTheDocument();
    });
  });

  // ── Toggle ─────────────────────────────────────────────────────────

  describe('Toggle', () => {
    it('calls onToggle when checkbox is clicked', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      fireEvent.click(screen.getByRole('checkbox'));
      expect(onToggle).toHaveBeenCalledWith(0);
    });

    it('calls onToggle with correct index', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} index={3} />);
      fireEvent.click(screen.getByRole('checkbox'));
      expect(onToggle).toHaveBeenCalledWith(3);
    });
  });

  // ── Title editing ──────────────────────────────────────────────────

  describe('Title editing', () => {
    it('enters edit mode when title is clicked', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      fireEvent.click(screen.getByText('Set up auth module'));
      expect(screen.getByDisplayValue('Set up auth module')).toBeInTheDocument();
    });

    it('commits title edit on Enter key', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      fireEvent.click(screen.getByText('Set up auth module'));
      const input = screen.getByDisplayValue('Set up auth module');
      fireEvent.change(input, { target: { value: 'Updated title' } });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(onEditTitle).toHaveBeenCalledWith(0, 'Updated title');
    });

    it('cancels title edit on Escape key without calling onEditTitle', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      fireEvent.click(screen.getByText('Set up auth module'));
      const input = screen.getByDisplayValue('Set up auth module');
      fireEvent.change(input, { target: { value: 'Changed' } });
      fireEvent.keyDown(input, { key: 'Escape' });
      expect(onEditTitle).not.toHaveBeenCalled();
    });

    it('does not commit title if text is empty', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      fireEvent.click(screen.getByText('Set up auth module'));
      const input = screen.getByDisplayValue('Set up auth module');
      fireEvent.change(input, { target: { value: '   ' } });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(onEditTitle).not.toHaveBeenCalled();
    });

    it('does not call onEditTitle if text unchanged', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      fireEvent.click(screen.getByText('Set up auth module'));
      const input = screen.getByDisplayValue('Set up auth module');
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(onEditTitle).not.toHaveBeenCalled();
    });
  });

  // ── Body editing ───────────────────────────────────────────────────

  describe('Body editing', () => {
    it('enters body edit mode when "Add details" is clicked', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ body: '', bodyLines: [] })} />);
      fireEvent.click(screen.getByText('Add details'));
      // Should show a textarea
      expect(screen.getByPlaceholderText('Task details (markdown supported)…')).toBeInTheDocument();
    });

    it('shows Save and Cancel buttons in body edit mode', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ body: '', bodyLines: [] })} />);
      fireEvent.click(screen.getByText('Add details'));
      expect(screen.getByText('Save')).toBeInTheDocument();
      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });

    it('commits body edit when Save is clicked', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ body: '', bodyLines: [] })} />);
      fireEvent.click(screen.getByText('Add details'));
      const textarea = screen.getByPlaceholderText('Task details (markdown supported)…');
      fireEvent.change(textarea, { target: { value: 'New body content' } });
      fireEvent.mouseDown(screen.getByText('Save'));
      expect(onEditBody).toHaveBeenCalledWith(0, 'New body content');
    });

    it('cancels body edit when Cancel is clicked', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ body: '', bodyLines: [] })} />);
      fireEvent.click(screen.getByText('Add details'));
      const textarea = screen.getByPlaceholderText('Task details (markdown supported)…');
      fireEvent.change(textarea, { target: { value: 'Should not be saved' } });
      fireEvent.mouseDown(screen.getByText('Cancel'));
      expect(onEditBody).not.toHaveBeenCalled();
    });

    it('expands body section when "Show details" is clicked', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ body: 'Hidden details' })} />);
      fireEvent.click(screen.getByText('Show details'));
      expect(screen.getByText('Hide details')).toBeInTheDocument();
      expect(screen.getByTestId('markdown-renderer')).toBeInTheDocument();
    });

    it('collapses body section when "Hide details" is clicked', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ body: 'Visible details' })} />);
      fireEvent.click(screen.getByText('Show details'));
      expect(screen.getByText('Hide details')).toBeInTheDocument();
      fireEvent.click(screen.getByText('Hide details'));
      expect(screen.getByText('Show details')).toBeInTheDocument();
    });

    it('enters body edit mode on double-click of rendered body', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask({ body: 'Body text' })} />);
      // First expand
      fireEvent.click(screen.getByText('Show details'));
      // Double-click the rendered body content container
      const bodyContainer = screen.getByTestId('markdown-renderer').parentElement!;
      fireEvent.doubleClick(bodyContainer);
      // Should show textarea
      expect(screen.getByPlaceholderText('Task details (markdown supported)…')).toBeInTheDocument();
    });
  });

  // ── Delete with confirmation ───────────────────────────────────────

  describe('Delete confirmation', () => {
    it('shows confirmation state on first delete click', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      // The delete button shows with "Delete task" title when not confirming
      const deleteButton = screen.getByTitle('Delete task');
      fireEvent.click(deleteButton);
      // Should now show confirm state
      expect(screen.getByTitle('Click again to confirm delete')).toBeInTheDocument();
    });

    it('calls onDelete on second click (confirm)', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      const deleteButton = screen.getByTitle('Delete task');
      fireEvent.click(deleteButton);
      const confirmButton = screen.getByTitle('Click again to confirm delete');
      fireEvent.click(confirmButton);
      expect(onDelete).toHaveBeenCalledWith(0);
    });

    it('auto-dismisses confirmation after 3 seconds', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      const deleteButton = screen.getByTitle('Delete task');
      fireEvent.click(deleteButton);
      expect(screen.getByTitle('Click again to confirm delete')).toBeInTheDocument();

      // Advance timer by 3 seconds inside act
      act(() => {
        vi.advanceTimersByTime(3000);
      });

      // Confirm button should be gone
      expect(screen.queryByTitle('Click again to confirm delete')).not.toBeInTheDocument();
    });
  });

  // ── Drag-and-drop ──────────────────────────────────────────────────

  describe('Drag-and-drop', () => {
    it('calls onDragStart when drag starts', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      const container = screen.getByText('Set up auth module').closest('[draggable]')!;
      fireEvent.dragStart(container, { dataTransfer: mockDataTransfer });
      expect(onDragStart).toHaveBeenCalledWith(0);
    });

    it('calls onDragEnd when drag ends', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      const container = screen.getByText('Set up auth module').closest('[draggable]')!;
      fireEvent.dragEnd(container);
      expect(onDragEnd).toHaveBeenCalled();
    });

    it('calls onDragOver when card is dragged over', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} index={2} />);
      const container = screen.getByText('Set up auth module').closest('[draggable]')!;
      fireEvent.dragOver(container, { dataTransfer: mockDataTransfer });
      expect(onDragOver).toHaveBeenCalledWith(2);
    });

    it('calls onDrop when an item is dropped', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} index={1} />);
      const container = screen.getByText('Set up auth module').closest('[draggable]')!;
      fireEvent.drop(container, { dataTransfer: mockDataTransfer });
      expect(onDrop).toHaveBeenCalledWith(1);
    });

    it('shows drag-over highlight when isDragOver is true', () => {
      const { container } = render(
        <DraggableTaskCard {...defaultProps} task={makeTask()} isDragOver={true} />
      );
      const cardDiv = container.firstChild as HTMLElement;
      expect(cardDiv.className).toContain('border-primary');
    });

    it('is not draggable when in title editing mode', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      // Enter title edit mode
      fireEvent.click(screen.getByText('Set up auth module'));
      const container = screen.getByDisplayValue('Set up auth module').closest('[draggable]')!;
      expect(container.getAttribute('draggable')).toBe('false');
    });
  });

  // ── Inline code rendering ──────────────────────────────────────────

  describe('Inline code rendering', () => {
    it('passes title through renderInlineCode when provided', () => {
      const renderInlineCode = (text: string) => [<span key="0" data-testid="inline-code">{text}</span>];
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} renderInlineCode={renderInlineCode} />);
      expect(screen.getByTestId('inline-code')).toBeInTheDocument();
      expect(screen.getByTestId('inline-code').textContent).toBe('Set up auth module');
    });

    it('renders plain title text when renderInlineCode not provided', () => {
      render(<DraggableTaskCard {...defaultProps} task={makeTask()} />);
      expect(screen.getByText('Set up auth module')).toBeInTheDocument();
    });
  });
});
