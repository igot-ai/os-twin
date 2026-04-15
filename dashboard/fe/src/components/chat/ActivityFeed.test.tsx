import { render, screen } from '@testing-library/react';
import { ActivityFeed } from './ActivityFeed';
import { useWebSocket } from '@/hooks/use-websocket';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';

vi.mock('@/hooks/use-websocket');

describe('ActivityFeed', () => {
  const mockUseWebSocket = useWebSocket as unknown as ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty state initially', () => {
    mockUseWebSocket.mockReturnValue({ lastMessage: null });
    render(<ActivityFeed />);
    expect(screen.getByText('Activity Feed')).toBeInTheDocument();
    expect(screen.getByText('No recent activity.')).toBeInTheDocument();
  });

  it('renders events based on websocket messages', () => {
    mockUseWebSocket.mockReturnValue({
      lastMessage: {
        type: 'error',
        detail: 'Something went wrong'
      }
    });

    render(<ActivityFeed />);
    expect(screen.getByText('Agent error: Something went wrong')).toBeInTheDocument();
  });
});
