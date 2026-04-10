import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import GitChangePanel from '../components/plan/files/GitChangePanel';
import { useFileChanges } from '../hooks/use-files';
import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('../hooks/use-files', () => ({
  useFileChanges: vi.fn(),
}));

describe('GitChangePanel Component', () => {
  const planId = 'plan-001';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state', () => {
    (useFileChanges as any).mockReturnValue({
      changes: undefined,
      isLoading: true,
      isError: undefined,
      refresh: vi.fn(),
    });

    render(<GitChangePanel planId={planId} />);
    expect(screen.getByText('Loading changes...')).toBeInTheDocument();
  });

  it('renders error state', () => {
    (useFileChanges as any).mockReturnValue({
      changes: undefined,
      isLoading: false,
      isError: new Error('Failed'),
      refresh: vi.fn(),
    });

    render(<GitChangePanel planId={planId} />);
    expect(screen.getByText('Error loading git changes')).toBeInTheDocument();
  });

  it('renders git-not-enabled state', () => {
    (useFileChanges as any).mockReturnValue({
      changes: { git_enabled: false, status: [], recent_commits: [] },
      isLoading: false,
      isError: undefined,
      refresh: vi.fn(),
    });

    render(<GitChangePanel planId={planId} />);
    expect(screen.getByText('Git Not Enabled')).toBeInTheDocument();
    expect(screen.getByText(/This project is not a git repository/)).toBeInTheDocument();
  });

  it('renders empty state when no pending changes', () => {
    (useFileChanges as any).mockReturnValue({
      changes: { git_enabled: true, status: [], recent_commits: [] },
      isLoading: false,
      isError: undefined,
      refresh: vi.fn(),
    });

    render(<GitChangePanel planId={planId} />);
    expect(screen.getByText('No pending changes')).toBeInTheDocument();
    expect(screen.getByText('UNSTAGED CHANGES (0)')).toBeInTheDocument();
  });

  it('renders file changes with status codes', () => {
    (useFileChanges as any).mockReturnValue({
      changes: {
        git_enabled: true,
        status: ['M  src/main.ts', 'A  src/new.ts', '?? untracked.txt'],
        recent_commits: [],
      },
      isLoading: false,
      isError: undefined,
      refresh: vi.fn(),
    });

    render(<GitChangePanel planId={planId} />);
    expect(screen.getByText('src/main.ts')).toBeInTheDocument();
    expect(screen.getByText('src/new.ts')).toBeInTheDocument();
    expect(screen.getByText('untracked.txt')).toBeInTheDocument();
    expect(screen.getByText('UNSTAGED CHANGES (3)')).toBeInTheDocument();
  });

  it('renders commit history', () => {
    (useFileChanges as any).mockReturnValue({
      changes: {
        git_enabled: true,
        status: [],
        recent_commits: [
          { hash: 'abc1234', subject: 'Initial commit', author: 'dev', timestamp: 1700000000 },
          { hash: 'def5678', subject: 'Add feature', author: 'dev2', timestamp: 1700100000 },
        ],
      },
      isLoading: false,
      isError: undefined,
      refresh: vi.fn(),
    });

    render(<GitChangePanel planId={planId} />);
    expect(screen.getByText('Initial commit')).toBeInTheDocument();
    expect(screen.getByText('Add feature')).toBeInTheDocument();
    expect(screen.getByText('abc1234')).toBeInTheDocument();
    expect(screen.getByText('def5678')).toBeInTheDocument();
    expect(screen.getByText('RECENT COMMITS (2)')).toBeInTheDocument();
  });

  it('renders "No commit history" when no commits', () => {
    (useFileChanges as any).mockReturnValue({
      changes: { git_enabled: true, status: [], recent_commits: [] },
      isLoading: false,
      isError: undefined,
      refresh: vi.fn(),
    });

    render(<GitChangePanel planId={planId} />);
    expect(screen.getByText('No commit history')).toBeInTheDocument();
  });

  it('renders author names in commits', () => {
    (useFileChanges as any).mockReturnValue({
      changes: {
        git_enabled: true,
        status: [],
        recent_commits: [
          { hash: 'aaa', subject: 'Fix bug', author: 'alice', timestamp: 1700000000 },
        ],
      },
      isLoading: false,
      isError: undefined,
      refresh: vi.fn(),
    });

    render(<GitChangePanel planId={planId} />);
    expect(screen.getByText('alice')).toBeInTheDocument();
  });

  it('renders Version Control header', () => {
    (useFileChanges as any).mockReturnValue({
      changes: { git_enabled: true, status: [], recent_commits: [] },
      isLoading: false,
      isError: undefined,
      refresh: vi.fn(),
    });

    render(<GitChangePanel planId={planId} />);
    expect(screen.getByText('Version Control')).toBeInTheDocument();
  });

  it('calls refresh when sync button is clicked', () => {
    const mockRefresh = vi.fn();
    (useFileChanges as any).mockReturnValue({
      changes: { git_enabled: true, status: [], recent_commits: [] },
      isLoading: false,
      isError: undefined,
      refresh: mockRefresh,
    });

    render(<GitChangePanel planId={planId} />);
    const refreshButton = screen.getByTitle('Refresh Git Status');
    fireEvent.click(refreshButton);
    expect(mockRefresh).toHaveBeenCalled();
  });
});
