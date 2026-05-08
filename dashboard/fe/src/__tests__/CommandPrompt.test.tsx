import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { CommandPrompt } from '../components/ui/CommandPrompt';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock image-utils to avoid canvas/FileReader issues in jsdom
vi.mock('@/lib/image-utils', () => ({
  processImages: vi.fn().mockResolvedValue({ images: [], errors: [] }),
  MAX_IMAGES: 10,
}));

describe('CommandPrompt Component', () => {
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the text input', () => {
    render(<CommandPrompt onSubmit={mockOnSubmit} />);
    const input = screen.getByPlaceholderText('What do you want to build?');
    expect(input).toBeInTheDocument();
  });

  it('renders the submit button', () => {
    render(<CommandPrompt onSubmit={mockOnSubmit} />);
    // Should have at least the add-image button and the submit button
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThanOrEqual(2);
    // Submit button has type="submit"
    const submitBtn = buttons.find(b => b.getAttribute('type') === 'submit');
    expect(submitBtn).toBeTruthy();
  });

  it('handles text input changes', () => {
    render(<CommandPrompt onSubmit={mockOnSubmit} />);
    const input = screen.getByPlaceholderText('What do you want to build?') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Build a todo app' } });
    expect(input.value).toBe('Build a todo app');
  });

  it('calls onSubmit when form is submitted with text', () => {
    render(<CommandPrompt onSubmit={mockOnSubmit} />);
    const input = screen.getByPlaceholderText('What do you want to build?');
    fireEvent.change(input, { target: { value: 'Build a todo app' } });

    // Submit the form
    const form = input.closest('form')!;
    fireEvent.submit(form);

    expect(mockOnSubmit).toHaveBeenCalledWith('Build a todo app', undefined);
  });

  it('does not submit when input is empty', () => {
    render(<CommandPrompt onSubmit={mockOnSubmit} />);
    const input = screen.getByPlaceholderText('What do you want to build?');

    const form = input.closest('form')!;
    fireEvent.submit(form);

    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  it('clears internal prompt after submit (uncontrolled)', () => {
    render(<CommandPrompt onSubmit={mockOnSubmit} />);
    const input = screen.getByPlaceholderText('What do you want to build?') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Build something' } });

    const form = input.closest('form')!;
    fireEvent.submit(form);

    expect(input.value).toBe('');
  });

  it('disables input when isLoading is true', () => {
    render(<CommandPrompt onSubmit={mockOnSubmit} isLoading={true} />);
    const input = screen.getByPlaceholderText('What do you want to build?');
    expect(input).toBeDisabled();
  });

  it('supports controlled mode with value and onChange', () => {
    const mockOnChange = vi.fn();
    render(
      <CommandPrompt
        onSubmit={mockOnSubmit}
        value="controlled text"
        onChange={mockOnChange}
      />
    );
    const input = screen.getByPlaceholderText('What do you want to build?') as HTMLInputElement;
    expect(input.value).toBe('controlled text');

    fireEvent.change(input, { target: { value: 'new text' } });
    expect(mockOnChange).toHaveBeenCalledWith('new text');
  });

  it('renders add image button', () => {
    render(<CommandPrompt onSubmit={mockOnSubmit} />);
    const addImageBtn = screen.getByLabelText('Add image');
    expect(addImageBtn).toBeInTheDocument();
  });

  it('disables add image button when isLoading', () => {
    render(<CommandPrompt onSubmit={mockOnSubmit} isLoading={true} />);
    const addImageBtn = screen.getByLabelText('Add image');
    expect(addImageBtn).toBeDisabled();
  });
});
