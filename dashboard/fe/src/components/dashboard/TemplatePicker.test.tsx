import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { TemplatePicker } from './TemplatePicker';
import { vi, describe, it, expect } from 'vitest';
import '@testing-library/jest-dom';

const mockCategories = [
  {
    id: 'engineering',
    name: 'Engineering',
    icon: 'engineering',
    templates: [
      { id: 't1', name: 'Frontend App', description: 'React App', promptTemplate: 'Build a React app' },
      { id: 't2', name: 'Backend API', description: 'Node API', promptTemplate: 'Build a Node API' },
    ]
  },
  {
    id: 'marketing',
    name: 'Marketing',
    icon: 'campaign',
    templates: [
      { id: 't3', name: 'Landing Page', description: 'SEO Page', promptTemplate: 'Build a Landing page' },
    ]
  }
];

describe('TemplatePicker', () => {
  it('renders all category tabs', () => {
    render(<TemplatePicker categories={mockCategories} onSelectTemplate={() => {}} />);
    expect(screen.getByText('Engineering')).toBeInTheDocument();
    expect(screen.getByText('Marketing')).toBeInTheDocument();
  });

  it('renders templates for the active tab', () => {
    render(<TemplatePicker categories={mockCategories} onSelectTemplate={() => {}} />);
    expect(screen.getByText('Frontend App')).toBeInTheDocument();
    expect(screen.getByText('Backend API')).toBeInTheDocument();
    expect(screen.queryByText('Landing Page')).not.toBeInTheDocument();
  });

  it('switches tabs on click', () => {
    render(<TemplatePicker categories={mockCategories} onSelectTemplate={() => {}} />);
    fireEvent.click(screen.getByText('Marketing'));
    expect(screen.getByText('Landing Page')).toBeInTheDocument();
    expect(screen.queryByText('Frontend App')).not.toBeInTheDocument();
  });

  it('calls onSelectTemplate when a template is clicked', () => {
    const onSelectTemplate = vi.fn();
    render(<TemplatePicker categories={mockCategories} onSelectTemplate={onSelectTemplate} />);
    fireEvent.click(screen.getByText('Frontend App'));
    expect(onSelectTemplate).toHaveBeenCalledWith('Build a React app');
  });

  it('renders a tooltip with the full prompt text for each template row, hidden by default', () => {
    render(<TemplatePicker categories={mockCategories} onSelectTemplate={() => {}} />);

    const tooltip = screen.getByText('Build a React app');
    // The Tooltip component hides itself until its wrapper is hovered, via
    // the `invisible group-hover:visible` class pair. Assert both classes so
    // we actually cover the hide/show behavior instead of just existence.
    expect(tooltip).toHaveClass('invisible');
    expect(tooltip.className).toMatch(/group-hover:visible/);

    // The wrapper must be the `group` owning the hover state, and must stretch
    // full-width so each row is not constrained by an inline-block tooltip.
    const wrapper = tooltip.closest('.group');
    expect(wrapper).not.toBeNull();
    expect(wrapper).toHaveClass('w-full');
  });

  describe('keyboard navigation', () => {
    const getTabs = () => screen.getAllByRole('tab');

    const focusTabList = () => {
      const activeTab = screen.getByRole('tab', { selected: true });
      activeTab.focus();
      return activeTab;
    };

    it('uses a roving tabindex so only the active tab is in the tab order', () => {
      render(<TemplatePicker categories={mockCategories} onSelectTemplate={() => {}} />);
      const [engineering, marketing] = getTabs();
      expect(engineering).toHaveAttribute('aria-selected', 'true');
      expect(engineering).toHaveAttribute('tabindex', '0');
      expect(marketing).toHaveAttribute('aria-selected', 'false');
      expect(marketing).toHaveAttribute('tabindex', '-1');
    });

    it('moves selection and DOM focus on ArrowRight/ArrowLeft', () => {
      render(<TemplatePicker categories={mockCategories} onSelectTemplate={() => {}} />);
      focusTabList();
      let [engineering, marketing] = getTabs();

      fireEvent.keyDown(engineering, { key: 'ArrowRight' });
      [engineering, marketing] = getTabs();
      expect(marketing).toHaveAttribute('aria-selected', 'true');
      expect(marketing).toHaveAttribute('tabindex', '0');
      expect(document.activeElement).toBe(marketing);
      // Panel content should have followed the selection.
      expect(screen.getByText('Landing Page')).toBeInTheDocument();
      expect(screen.queryByText('Frontend App')).not.toBeInTheDocument();

      fireEvent.keyDown(marketing, { key: 'ArrowLeft' });
      [engineering, marketing] = getTabs();
      expect(engineering).toHaveAttribute('aria-selected', 'true');
      expect(document.activeElement).toBe(engineering);
      expect(screen.getByText('Frontend App')).toBeInTheDocument();
    });

    it('wraps with ArrowLeft on the first tab and with ArrowRight on the last tab', () => {
      render(<TemplatePicker categories={mockCategories} onSelectTemplate={() => {}} />);
      focusTabList();
      let [engineering, marketing] = getTabs();

      fireEvent.keyDown(engineering, { key: 'ArrowLeft' });
      [, marketing] = getTabs();
      expect(marketing).toHaveAttribute('aria-selected', 'true');
      expect(document.activeElement).toBe(marketing);

      fireEvent.keyDown(marketing, { key: 'ArrowRight' });
      [engineering] = getTabs();
      expect(engineering).toHaveAttribute('aria-selected', 'true');
      expect(document.activeElement).toBe(engineering);
    });

    it('jumps to first/last with Home/End', () => {
      render(<TemplatePicker categories={mockCategories} onSelectTemplate={() => {}} />);
      focusTabList();
      let [engineering, marketing] = getTabs();

      fireEvent.keyDown(engineering, { key: 'End' });
      [, marketing] = getTabs();
      expect(marketing).toHaveAttribute('aria-selected', 'true');
      expect(document.activeElement).toBe(marketing);

      fireEvent.keyDown(marketing, { key: 'Home' });
      [engineering] = getTabs();
      expect(engineering).toHaveAttribute('aria-selected', 'true');
      expect(document.activeElement).toBe(engineering);
    });
  });

  it('renders nothing when no categories are provided', () => {
    const { container } = render(<TemplatePicker categories={[]} onSelectTemplate={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
