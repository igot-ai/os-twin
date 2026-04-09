import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { TemplateProgress } from './TemplateProgress';
import { vi, describe, it, expect } from 'vitest';
import '@testing-library/jest-dom';

describe('TemplateProgress', () => {
  const defaultProps = {
    templateName: 'Web App',
    total: 6,
    filled: 3,
    percent: 50,
    unfilledLabels: ['Audience', 'Tech stack', 'Done when'],
    onEdit: vi.fn(),
    onClear: vi.fn(),
  };

  it('renders template name and progress', () => {
    render(<TemplateProgress {...defaultProps} />);
    expect(screen.getByText('Web App')).toBeInTheDocument();
    expect(screen.getByText('3/6')).toBeInTheDocument();
  });

  it('shows unfilled hints when percent < 50', () => {
    render(<TemplateProgress {...defaultProps} percent={30} />);
    expect(screen.getByText(/Still needed/)).toBeInTheDocument();
    expect(screen.getByText(/Audience/)).toBeInTheDocument();
  });

  it('hides unfilled hints when percent >= 50', () => {
    render(<TemplateProgress {...defaultProps} />);
    expect(screen.queryByText(/Still needed/)).not.toBeInTheDocument();
  });

  it('calls onEdit when tune button is clicked', () => {
    const onEdit = vi.fn();
    render(<TemplateProgress {...defaultProps} onEdit={onEdit} />);
    fireEvent.click(screen.getByLabelText('Edit template fields'));
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it('calls onClear when close button is clicked', () => {
    const onClear = vi.fn();
    render(<TemplateProgress {...defaultProps} onClear={onClear} />);
    fireEvent.click(screen.getByLabelText('Clear template'));
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it('renders nothing when total is 0', () => {
    const { container } = render(
      <TemplateProgress {...defaultProps} total={0} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
