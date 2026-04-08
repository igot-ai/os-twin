import React from 'react';
import { render, screen } from '@testing-library/react';
import { AgentResponse } from './AgentResponse';
import { vi, describe, it, expect } from 'vitest';
import '@testing-library/jest-dom';

vi.mock('@/lib/markdown-renderer', () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div>{content}</div>
}));

describe('AgentResponse', () => {
  it('renders content correctly', () => {
    render(<AgentResponse content="Test message content" />);
    expect(screen.getByText('Test message content')).toBeInTheDocument();
  });

  it('renders streaming indicator when streaming', () => {
    const { container } = render(<AgentResponse content="Streaming text" isStreaming={true} />);
    expect(screen.getByText('Streaming text')).toBeInTheDocument();
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });
});
