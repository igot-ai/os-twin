import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { IdeaChat } from '../components/ideas/IdeaChat';
import { usePlanningThread } from '../hooks/use-planning-thread';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';

vi.mock('../hooks/use-planning-thread', () => ({
  usePlanningThread: vi.fn()
}));

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/ideas/test-id',
  useParams: () => ({ threadId: 'test-id' })
}));

describe('IdeaChat Component', () => {
  const mockUsePlanningThread = usePlanningThread as unknown as ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom does not implement scrollIntoView
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    mockUsePlanningThread.mockReturnValue({
      thread: null,
      messages: [],
      streamedResponse: '',
      isStreaming: false,
      isLoading: false,
      sendMessage: vi.fn(),
      promoteToPlan: vi.fn(),
      cancel: vi.fn()
    });
  });

  it('renders empty state with chips', () => {
    render(<IdeaChat threadId="test-id" />);
    
    expect(screen.getByText('New Idea')).toBeInTheDocument();
    expect(screen.getByText('What problem does this solve?')).toBeInTheDocument();
    expect(screen.getByText('Who are the users?')).toBeInTheDocument();
  });

  it('renders messages and no chips', () => {
    mockUsePlanningThread.mockReturnValue({
      thread: { title: 'Test Thread', status: 'active' },
      messages: [{ id: '1', role: 'user', content: 'Hello', created_at: 'now' }],
      streamedResponse: '',
      isStreaming: false,
      isLoading: false,
      sendMessage: vi.fn(),
      promoteToPlan: vi.fn(),
      cancel: vi.fn()
    });

    render(<IdeaChat threadId="test-id" />);
    
    expect(screen.getByText('Test Thread')).toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.queryByText('What problem does this solve?')).not.toBeInTheDocument();
  });

  it('handles sending a message', () => {
    const sendMessage = vi.fn();
    mockUsePlanningThread.mockReturnValue({
      thread: null,
      messages: [],
      streamedResponse: '',
      isStreaming: false,
      isLoading: false,
      sendMessage,
      promoteToPlan: vi.fn(),
      cancel: vi.fn()
    });

    render(<IdeaChat threadId="test-id" />);
    
    const input = screen.getByPlaceholderText(/Type your message/i) as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: 'Test message' } });
    
    const sendIcon = screen.getByText('send');
    fireEvent.click(sendIcon);
    
    expect(sendMessage).toHaveBeenCalledWith('Test message', undefined);
  });
});
