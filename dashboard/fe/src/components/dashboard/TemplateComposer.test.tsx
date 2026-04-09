import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { TemplateComposer } from './TemplateComposer';
import { vi, describe, it, expect } from 'vitest';
import '@testing-library/jest-dom';
import type { PromptTemplate } from '@/data/prompt-templates';

const mockTemplate: PromptTemplate = {
  id: 'test-tpl',
  name: 'Test Template',
  description: 'A test template',
  promptTemplate: '# {{name}}\n## Goal\n{{ }}',
  fields: [
    { id: 'field-0', label: 'Project name', hint: 'name', type: 'short', required: true, group: 'basics' },
    { id: 'field-1', label: 'Goal', hint: '', type: 'short', required: true, group: 'goal' },
  ],
  groups: [
    { id: 'basics', label: 'The basics' },
    { id: 'goal', label: 'Goal' },
  ],
};

describe('TemplateComposer', () => {
  const defaultProps = {
    template: mockTemplate,
    fieldValues: {},
    onFieldChange: vi.fn(),
    onFinish: vi.fn(),
    onCancel: vi.fn(),
    completeness: { total: 2, filled: 0, percent: 0 },
  };

  it('renders the template name and description', () => {
    render(<TemplateComposer {...defaultProps} />);
    expect(screen.getByText('Test Template')).toBeInTheDocument();
    expect(screen.getByText('A test template')).toBeInTheDocument();
  });

  it('renders group tabs when there are multiple groups', () => {
    render(<TemplateComposer {...defaultProps} />);
    expect(screen.getByText('The basics')).toBeInTheDocument();
    expect(screen.getByText('Goal')).toBeInTheDocument();
  });

  it('renders fields for the active group', () => {
    render(<TemplateComposer {...defaultProps} />);
    // First group is active by default
    expect(screen.getByText('Project name')).toBeInTheDocument();
  });

  it('switches group tab on click and shows its fields', () => {
    render(<TemplateComposer {...defaultProps} />);
    // Click the "Goal" tab (use getAllByText since "Goal" appears as both tab and field label)
    const goalElements = screen.getAllByText('Goal');
    // The tab is the button element
    const goalTab = goalElements.find(el => el.closest('button')?.className.includes('border-b-2'));
    expect(goalTab).toBeDefined();
    fireEvent.click(goalTab!);
    // After clicking, the Goal tab should be active (has primary color class)
    expect(goalTab!.closest('button')!.className).toContain('border-[var(--color-primary)]');
  });

  it('calls onFieldChange when user types in a field', () => {
    const onFieldChange = vi.fn();
    render(<TemplateComposer {...defaultProps} onFieldChange={onFieldChange} />);
    const input = screen.getByPlaceholderText('name');
    fireEvent.change(input, { target: { value: 'MyApp' } });
    expect(onFieldChange).toHaveBeenCalledWith('field-0', 'MyApp');
  });

  it('calls onFinish when "Use template" is clicked', () => {
    const onFinish = vi.fn();
    render(
      <TemplateComposer
        {...defaultProps}
        onFinish={onFinish}
        completeness={{ total: 2, filled: 1, percent: 50 }}
      />
    );
    fireEvent.click(screen.getByText('Use template'));
    expect(onFinish).toHaveBeenCalledTimes(1);
  });

  it('disables "Use template" when nothing is filled', () => {
    render(<TemplateComposer {...defaultProps} />);
    const btn = screen.getByText('Use template').closest('button');
    expect(btn).toBeDisabled();
  });

  it('calls onCancel when close button is clicked', () => {
    const onCancel = vi.fn();
    render(<TemplateComposer {...defaultProps} onCancel={onCancel} />);
    fireEvent.click(screen.getByLabelText('Cancel template'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('shows required field count in footer', () => {
    render(<TemplateComposer {...defaultProps} />);
    expect(screen.getByText('2 required fields remaining')).toBeInTheDocument();
  });

  it('shows "All required fields filled" when everything is filled', () => {
    render(
      <TemplateComposer
        {...defaultProps}
        fieldValues={{ 'field-0': 'App', 'field-1': 'Build stuff' }}
        completeness={{ total: 2, filled: 2, percent: 100 }}
      />
    );
    expect(screen.getByText('All required fields filled')).toBeInTheDocument();
  });

  it('shows completeness fraction in header', () => {
    render(
      <TemplateComposer
        {...defaultProps}
        completeness={{ total: 2, filled: 1, percent: 50 }}
      />
    );
    expect(screen.getByText('1/2')).toBeInTheDocument();
  });
});
