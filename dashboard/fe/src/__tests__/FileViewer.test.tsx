import React from 'react';
import { render, screen } from '@testing-library/react';
import FileViewer from '../components/plan/files/FileViewer';
import { useFileContent } from '../hooks/use-files';
import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('../hooks/use-files', () => ({
  useFileContent: vi.fn(),
}));

describe('FileViewer Component', () => {
  const planId = 'plan-001';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty state when no path is selected', () => {
    (useFileContent as any).mockReturnValue({
      content: undefined,
      isLoading: false,
      isError: undefined,
    });

    render(<FileViewer planId={planId} path={null} />);
    expect(screen.getByText('Select a file to view its content')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    (useFileContent as any).mockReturnValue({
      content: undefined,
      isLoading: true,
      isError: undefined,
    });

    render(<FileViewer planId={planId} path="src/main.ts" />);
    // Loading state shows skeleton (animate-pulse divs), not text
    const container = document.querySelector('.animate-pulse');
    expect(container).toBeTruthy();
  });

  it('renders error state when fetch fails', () => {
    (useFileContent as any).mockReturnValue({
      content: undefined,
      isLoading: false,
      isError: new Error('Not found'),
    });

    render(<FileViewer planId={planId} path="src/missing.ts" />);
    expect(screen.getByText('Failed to load file')).toBeInTheDocument();
    expect(screen.getByText('src/missing.ts')).toBeInTheDocument();
  });

  it('renders error state when content is null', () => {
    (useFileContent as any).mockReturnValue({
      content: null,
      isLoading: false,
      isError: undefined,
    });

    render(<FileViewer planId={planId} path="src/empty.ts" />);
    expect(screen.getByText('Failed to load file')).toBeInTheDocument();
  });

  it('renders text file content', () => {
    (useFileContent as any).mockReturnValue({
      content: {
        path: 'src/main.ts',
        content: 'console.log("hello world");',
        encoding: 'utf-8',
        size: 27,
        mime_type: 'text/typescript',
        truncated: false,
      },
      isLoading: false,
      isError: undefined,
    });

    render(<FileViewer planId={planId} path="src/main.ts" />);
    expect(screen.getByText('console.log("hello world");')).toBeInTheDocument();
    expect(screen.getByText('main.ts')).toBeInTheDocument();
  });

  it('renders file size information', () => {
    (useFileContent as any).mockReturnValue({
      content: {
        path: 'src/main.ts',
        content: 'hello',
        encoding: 'utf-8',
        size: 5,
        mime_type: 'text/plain',
        truncated: false,
      },
      isLoading: false,
      isError: undefined,
    });

    render(<FileViewer planId={planId} path="src/main.ts" />);
    expect(screen.getByText('5 B')).toBeInTheDocument();
  });

  it('renders truncated indicator when file is truncated', () => {
    (useFileContent as any).mockReturnValue({
      content: {
        path: 'src/big.ts',
        content: 'partial content...',
        encoding: 'utf-8',
        size: 1000000,
        mime_type: 'text/typescript',
        truncated: true,
      },
      isLoading: false,
      isError: undefined,
    });

    render(<FileViewer planId={planId} path="src/big.ts" />);
    expect(screen.getByText('TRUNCATED')).toBeInTheDocument();
  });

  it('renders binary file message for base64 non-image content', () => {
    (useFileContent as any).mockReturnValue({
      content: {
        path: 'data.bin',
        content: 'AQID', // some base64 data
        encoding: 'base64',
        size: 3,
        mime_type: 'application/octet-stream',
        truncated: false,
      },
      isLoading: false,
      isError: undefined,
    });

    render(<FileViewer planId={planId} path="data.bin" />);
    expect(screen.getByText('Binary File')).toBeInTheDocument();
    expect(screen.getByText('This file cannot be displayed as text.')).toBeInTheDocument();
    expect(screen.getByText('Download File')).toBeInTheDocument();
  });

  it('renders image for image mime types', () => {
    (useFileContent as any).mockReturnValue({
      content: {
        path: 'logo.png',
        content: 'iVBORw0KGgoAAAANSUhEUg==', // stub base64
        encoding: 'base64',
        size: 100,
        mime_type: 'image/png',
        truncated: false,
      },
      isLoading: false,
      isError: undefined,
    });

    render(<FileViewer planId={planId} path="logo.png" />);
    const img = screen.getByAltText('logo.png');
    expect(img).toBeInTheDocument();
    expect(img.getAttribute('src')).toContain('data:image/png;base64,');
  });
});
