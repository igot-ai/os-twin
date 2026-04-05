import React from 'react';
import { render, screen } from '@testing-library/react';
import { ChatHistory } from './ChatHistory';
import { useConversation } from '@/hooks/use-conversation';
import '@testing-library/jest-dom';

// Mock the hook
jest.mock('@/hooks/use-conversation');

// Mock MarkdownRenderer to avoid complexity
jest.mock('@/lib/markdown-renderer', () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div>{content}</div>
}));

describe('ChatHistory', () => {
  const mockUseConversation = useConversation as jest.Mock;

  beforeEach(() => {
    // Basic setup for scrollIntoView
    window.HTMLElement.prototype.scrollIntoView = jest.fn();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('renders loading state when loading and no data', () => {
    mockUseConversation.mockReturnValue({
      conversation: null,
      isLoading: true
    });

    render(<ChatHistory conversationId="conv-1" />);
    // Loading spinner should be rendered
    expect(screen.getByTestId('loading-container')).toBeInTheDocument();
  });

  it('renders messages correctly', () => {
    mockUseConversation.mockReturnValue({
      conversation: {
        id: 'conv-1',
        title: 'Test Conv',
        messages: [
          { id: 'm1', role: 'user', content: 'Hello' },
          { id: 'm2', role: 'assistant', content: 'Hi there!' }
        ]
      },
      isLoading: false
    });

    render(<ChatHistory conversationId="conv-1" />);

    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('Hi there!')).toBeInTheDocument();
  });

  it('renders streaming message if provided', () => {
    mockUseConversation.mockReturnValue({
      conversation: {
        id: 'conv-1',
        messages: []
      },
      isLoading: false
    });

    render(<ChatHistory conversationId="conv-1" streamingMessage="Streaming..." />);
    
    expect(screen.getByText('Streaming...')).toBeInTheDocument();
  });
});
