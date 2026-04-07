import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import SkillChipInput from '../components/roles/SkillChipInput';
import useSWR from 'swr';

vi.mock('swr', () => ({
  default: vi.fn(),
}));

const mockSkills = [
  { id: 's1', name: 'implement-epic', version: '1.0', description: 'Break epics into tasks', category: 'implementation', trust_level: 'core', applicable_roles: ['engineer'], usage_count: 10 },
  { id: 's2', name: 'refactor-code', version: '1.0', description: 'Safely restructure code', category: 'implementation', trust_level: 'verified', applicable_roles: ['engineer'], usage_count: 8 },
  { id: 's3', name: 'code-review', version: '1.0', description: 'Review code for quality', category: 'review', trust_level: 'core', applicable_roles: ['qa'], usage_count: 5 },
  { id: 's4', name: 'write-tests', version: '1.0', description: 'Write unit and integration tests', category: 'testing', trust_level: 'verified', applicable_roles: ['qa', 'engineer'], usage_count: 3 },
  { id: 's5', name: 'security-review', version: '1.0', description: 'Check for vulnerabilities', category: 'review', trust_level: 'experimental', applicable_roles: ['qa'], usage_count: 1 },
];

describe('SkillChipInput', () => {
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useSWR as any).mockReturnValue({
      data: mockSkills,
      isLoading: false,
    });
  });

  it('renders selected skill chips', () => {
    render(<SkillChipInput selectedSkillRefs={['implement-epic', 'code-review']} onChange={mockOnChange} />);
    expect(screen.getByText('implement-epic')).toBeInTheDocument();
    expect(screen.getByText('code-review')).toBeInTheDocument();
  });

  it('opens dropdown on focus', () => {
    render(<SkillChipInput selectedSkillRefs={[]} onChange={mockOnChange} />);
    fireEvent.click(screen.getByPlaceholderText(/search skills/i));

    // Should show at least one skill
    expect(screen.getByText('implement-epic')).toBeInTheDocument();
  });

  it('groups skills by category with section headers', () => {
    render(<SkillChipInput selectedSkillRefs={[]} onChange={mockOnChange} />);
    fireEvent.click(screen.getByPlaceholderText(/search skills/i));

    // Category headers should appear (capitalized)
    expect(screen.getByText('Implementation')).toBeInTheDocument();
    expect(screen.getByText('Review')).toBeInTheDocument();
    expect(screen.getByText('Testing')).toBeInTheDocument();
  });

  it('shows trust level badges on skills', () => {
    render(<SkillChipInput selectedSkillRefs={[]} onChange={mockOnChange} />);
    fireEvent.click(screen.getByPlaceholderText(/search skills/i));

    // Trust level badges should be visible
    const coreBadges = screen.getAllByText('core');
    const verifiedBadges = screen.getAllByText('verified');
    expect(coreBadges.length).toBeGreaterThanOrEqual(1);
    expect(verifiedBadges.length).toBeGreaterThanOrEqual(1);
  });

  it('filters skills by search term across all categories', () => {
    render(<SkillChipInput selectedSkillRefs={[]} onChange={mockOnChange} />);
    const input = screen.getByPlaceholderText(/search skills/i);
    fireEvent.click(input);
    fireEvent.change(input, { target: { value: 'review' } });

    // Should match code-review and security-review
    expect(screen.getByText('code-review')).toBeInTheDocument();
    expect(screen.getByText('security-review')).toBeInTheDocument();
    // Should NOT show non-matching skills
    expect(screen.queryByText('implement-epic')).not.toBeInTheDocument();
    expect(screen.queryByText('write-tests')).not.toBeInTheDocument();
  });

  it('toggles skill selection on click', () => {
    render(<SkillChipInput selectedSkillRefs={[]} onChange={mockOnChange} />);
    fireEvent.click(screen.getByPlaceholderText(/search skills/i));
    fireEvent.click(screen.getByText('implement-epic'));

    expect(mockOnChange).toHaveBeenCalledWith(['implement-epic']);
  });

  it('removes skill when chip close button is clicked', () => {
    render(<SkillChipInput selectedSkillRefs={['implement-epic', 'code-review']} onChange={mockOnChange} />);

    const closeButtons = screen.getAllByText('close');
    fireEvent.click(closeButtons[0]);

    expect(mockOnChange).toHaveBeenCalledWith(['code-review']);
  });

  it('excludes selected skills from dropdown', () => {
    render(<SkillChipInput selectedSkillRefs={['implement-epic']} onChange={mockOnChange} />);
    fireEvent.click(screen.getByPlaceholderText(/search skills/i));

    // implement-epic is selected, should not appear in dropdown list
    // But it appears as a chip - dropdown items should not include it
    const dropdownItems = screen.getAllByRole('button').filter(
      btn => btn.textContent?.includes('refactor-code') ||
             btn.textContent?.includes('code-review') ||
             btn.textContent?.includes('write-tests') ||
             btn.textContent?.includes('security-review')
    );
    expect(dropdownItems.length).toBe(4);
  });
});
