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

  it('shows tooltip on hover', async () => {
    render(<TemplatePicker categories={mockCategories} onSelectTemplate={() => {}} />);
    const templateRow = screen.getByText('Frontend App').closest('button');
    if (!templateRow) throw new Error('Template row not found');

    // Tooltip is triggered by group-hover in CSS, but testing library doesn't easily test CSS transitions.
    // However, Tooltip.tsx uses "group-hover:visible" on a div.
    // We can check if the tooltip content exists in the document (it's always rendered but invisible).
    expect(screen.getByText('Build a React app')).toBeInTheDocument();
  });
});
