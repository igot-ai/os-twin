import { render, screen } from '@testing-library/react';
import { ActivityFeed } from './ActivityFeed';
import { usePlanningThreads } from '@/hooks/use-planning-threads';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';

vi.mock('@/hooks/use-planning-threads');

describe('ActivityFeed', () => {
  const mockUsePlanningThreads = usePlanningThreads as unknown as ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty state initially', () => {
    mockUsePlanningThreads.mockReturnValue({ threads: [], isLoading: false });
    render(<ActivityFeed />);
    expect(screen.getByText('Recent Ideas')).toBeInTheDocument();
    expect(screen.getByText('No ideas yet. Start brainstorming above!')).toBeInTheDocument();
  });

  it('renders ideas from threads', () => {
    mockUsePlanningThreads.mockReturnValue({
      threads: [
        {
          id: 'thread-1',
          title: 'Test Idea',
          created_at: new Date().toISOString(),
          message_count: 5
        }
      ],
      isLoading: false
    });

    render(<ActivityFeed />);
    expect(screen.getByText('Test Idea')).toBeInTheDocument();
    expect(screen.getByText('5 messages')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    mockUsePlanningThreads.mockReturnValue({ threads: [], isLoading: true });
    render(<ActivityFeed />);
    // Should show skeletons (represented by div with skeleton class)
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
