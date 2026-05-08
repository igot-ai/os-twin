/**
 * Unit tests for DraggableChecklistItem component.
 *
 * Tests the reusable checklist item component with drag handle, checkbox,
 * inline editing, delete confirmation, and keyboard support.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DraggableChecklistItem } from '../components/plan/DraggableChecklistItem';
import { CheckItem } from '@/lib/epic-parser';

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

// ── Test data ────────────────────────────────────────────────────────────

function makeItem(overrides: Partial<CheckItem> = {}): CheckItem {
  return {
    text: 'Test item',
    checked: false,
    rawLine: '- [ ] Test item',
    prefix: '- [ ] ',
    ...overrides,
  };
}

// ── Tests ────────────────────────────────────────────────────────────────

describe('DraggableChecklistItem', () => {
  const onToggle = vi.fn();
  const onEdit = vi.fn();
  const onDelete = vi.fn();
  const onDragStart = vi.fn();
  const onDragEnd = vi.fn();
  const onDragOver = vi.fn();
  const onDrop = vi.fn();
  const onNextItem = vi.fn();

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
    isAC: false,
    onToggle,
    onEdit,
    onDelete,
    onDragStart,
    onDragEnd,
    onDragOver,
    onDrop,
    onNextItem,
  };

  // ── Rendering ──────────────────────────────────────────────────────────

  describe('Rendering', () => {
    it('renders the item text', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      expect(screen.getByText('Test item')).toBeInTheDocument();
    });

    it('renders a checkbox with correct checked state', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem({ checked: true })} />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeChecked();
    });

    it('renders unchecked checkbox for unchecked item', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem({ checked: false })} />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).not.toBeChecked();
    });

    it('renders a drag handle with drag_indicator icon', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      expect(screen.getByText('drag_indicator')).toBeInTheDocument();
    });

    it('applies line-through style to checked items when not AC', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem({ checked: true })} isAC={false} />);
      const textSpan = screen.getByText('Test item');
      expect(textSpan.className).toContain('line-through');
    });

    it('applies success style to checked items when AC', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem({ checked: true })} isAC={true} />);
      const textSpan = screen.getByText('Test item');
      expect(textSpan.className).toContain('text-success-text');
    });
  });

  // ── Toggle ─────────────────────────────────────────────────────────────

  describe('Toggle', () => {
    it('calls onToggle when checkbox is clicked', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      fireEvent.click(screen.getByRole('checkbox'));
      expect(onToggle).toHaveBeenCalledWith(0);
    });

    it('calls onToggle with correct index', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} index={3} />);
      fireEvent.click(screen.getByRole('checkbox'));
      expect(onToggle).toHaveBeenCalledWith(3);
    });
  });

  // ── Inline editing ────────────────────────────────────────────────────

  describe('Inline editing', () => {
    it('enters edit mode when text is clicked', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      fireEvent.click(screen.getByText('Test item'));
      // Should show an input field
      expect(screen.getByDisplayValue('Test item')).toBeInTheDocument();
    });

    it('commits edit on Enter key', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      fireEvent.click(screen.getByText('Test item'));
      const input = screen.getByDisplayValue('Test item');
      fireEvent.change(input, { target: { value: 'Updated item' } });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(onEdit).toHaveBeenCalledWith(0, 'Updated item');
    });

    it('cancels edit on Escape key without calling onEdit', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      fireEvent.click(screen.getByText('Test item'));
      const input = screen.getByDisplayValue('Test item');
      fireEvent.change(input, { target: { value: 'Changed' } });
      fireEvent.keyDown(input, { key: 'Escape' });
      expect(onEdit).not.toHaveBeenCalled();
    });

    it('commits edit on Tab key and calls onNextItem', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      fireEvent.click(screen.getByText('Test item'));
      const input = screen.getByDisplayValue('Test item');
      fireEvent.change(input, { target: { value: 'Tabbed item' } });
      fireEvent.keyDown(input, { key: 'Tab' });
      expect(onEdit).toHaveBeenCalledWith(0, 'Tabbed item');
      expect(onNextItem).toHaveBeenCalled();
    });

    it('does not commit if text is empty', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      fireEvent.click(screen.getByText('Test item'));
      const input = screen.getByDisplayValue('Test item');
      fireEvent.change(input, { target: { value: '   ' } });
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(onEdit).not.toHaveBeenCalled();
    });

    it('does not call onEdit if text unchanged', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      fireEvent.click(screen.getByText('Test item'));
      const input = screen.getByDisplayValue('Test item');
      fireEvent.keyDown(input, { key: 'Enter' });
      expect(onEdit).not.toHaveBeenCalled();
    });
  });

  // ── Delete with confirmation ───────────────────────────────────────────

  describe('Delete confirmation', () => {
    it('shows confirmation state on first delete click', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      const deleteButtons = screen.getAllByTitle(/Delete/i);
      const deleteButton = deleteButtons.find(btn => btn.textContent?.includes('close') || btn.textContent?.includes('delete'));
      expect(deleteButton).toBeTruthy();
      fireEvent.click(deleteButton!);
      // Should now show confirm state with delete icon
      expect(screen.getByTitle('Click again to confirm delete')).toBeInTheDocument();
    });

    it('calls onDelete on second click (confirm)', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      const closeButton = screen.getByTitle('Delete item');
      fireEvent.click(closeButton);
      const confirmButton = screen.getByTitle('Click again to confirm delete');
      fireEvent.click(confirmButton);
      expect(onDelete).toHaveBeenCalledWith(0);
    });

    it('auto-dismisses confirmation after 3 seconds', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      const closeButton = screen.getByTitle('Delete item');
      fireEvent.click(closeButton);
      expect(screen.getByTitle('Click again to confirm delete')).toBeInTheDocument();

      // Advance timer by 3 seconds inside act
      act(() => {
        vi.advanceTimersByTime(3000);
      });

      // Confirm button should be gone
      expect(screen.queryByTitle('Click again to confirm delete')).not.toBeInTheDocument();
    });
  });

  // ── Drag-and-drop ──────────────────────────────────────────────────────

  describe('Drag-and-drop', () => {
    it('calls onDragStart when drag starts', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      const container = screen.getByText('Test item').closest('[draggable]')!;
      fireEvent.dragStart(container, { dataTransfer: mockDataTransfer });
      expect(onDragStart).toHaveBeenCalledWith(0);
    });

    it('calls onDragEnd when drag ends', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      const container = screen.getByText('Test item').closest('[draggable]')!;
      fireEvent.dragEnd(container);
      expect(onDragEnd).toHaveBeenCalled();
    });

    it('calls onDragOver when item is dragged over', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} index={2} />);
      const container = screen.getByText('Test item').closest('[draggable]')!;
      fireEvent.dragOver(container, { dataTransfer: mockDataTransfer });
      expect(onDragOver).toHaveBeenCalledWith(2);
    });

    it('calls onDrop when an item is dropped', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} index={1} />);
      const container = screen.getByText('Test item').closest('[draggable]')!;
      fireEvent.drop(container, { dataTransfer: mockDataTransfer });
      expect(onDrop).toHaveBeenCalledWith(1);
    });

    it('shows drag-over highlight when isDragOver is true', () => {
      const { container } = render(
        <DraggableChecklistItem {...defaultProps} item={makeItem()} isDragOver={true} />
      );
      const itemDiv = container.firstChild as HTMLElement;
      expect(itemDiv.className).toContain('bg-primary');
    });

    it('is not draggable when in editing mode', () => {
      render(<DraggableChecklistItem {...defaultProps} item={makeItem()} />);
      // Enter edit mode
      fireEvent.click(screen.getByText('Test item'));
      // The outer div should have draggable="false"
      const container = screen.getByDisplayValue('Test item').closest('[draggable]')!;
      expect(container.getAttribute('draggable')).toBe('false');
    });
  });
});
