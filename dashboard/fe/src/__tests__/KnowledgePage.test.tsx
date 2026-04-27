/**
 * Tests for KnowledgePage (Global Knowledge Base).
 * Using Vitest + React Testing Library.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import KnowledgePage from '@/app/knowledge/page';

// Mock ResizeObserver for jsdom
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;

// Mock the hooks
vi.mock('@/hooks/use-knowledge-namespaces', () => ({
  useKnowledgeNamespaces: vi.fn(() => ({
    namespaces: [
      {
        schema_version: 1,
        name: 'test-namespace',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        language: 'English',
        description: 'Test namespace',
        embedding_model: 'text-embedding-3-small',
        embedding_dimension: 1536,
        stats: {
          files_indexed: 10,
          chunks: 100,
          entities: 50,
          relations: 25,
          vectors: 100,
          bytes_on_disk: 1024000,
        },
        imports: [],
      },
      {
        schema_version: 1,
        name: 'another-namespace',
        created_at: '2024-01-02T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
        language: 'English',
        description: null,
        embedding_model: 'text-embedding-3-small',
        embedding_dimension: 1536,
        stats: {
          files_indexed: 0,
          chunks: 0,
          entities: 0,
          relations: 0,
          vectors: 0,
          bytes_on_disk: 0,
        },
        imports: [],
      },
    ],
    isLoading: false,
    isError: null,
    createNamespace: vi.fn(),
    refresh: vi.fn(),
  })),
}));

vi.mock('@/hooks/use-knowledge-import', () => ({
  useKnowledgeImportMonitor: vi.fn(() => ({
    jobs: [],
    activeJob: undefined,
    isLoading: false,
    startImport: vi.fn(),
    refreshJobs: vi.fn(),
  })),
}));

vi.mock('@/hooks/use-knowledge-query', () => ({
  useKnowledgeQuery: vi.fn(() => ({
    result: null,
    isLoading: false,
    error: null,
    executeQuery: vi.fn(),
    clearResult: vi.fn(),
  })),
}));

vi.mock('@/hooks/use-knowledge-graph', () => ({
  useKnowledgeGraph: vi.fn(() => ({
    nodes: [],
    edges: [],
    stats: { node_count: 0, edge_count: 0 },
    isLoading: false,
    refresh: vi.fn(),
  })),
}));

vi.mock('@/lib/stores/notificationStore', () => ({
  useNotificationStore: vi.fn((selector) => {
    const state = { addToast: vi.fn() };
    return selector ? selector(state) : state;
  }),
}));

// Mock next/navigation
const mockSearchParams = new URLSearchParams();
vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(() => mockSearchParams),
  useRouter: vi.fn(() => ({
    push: vi.fn(),
  })),
}));

describe('KnowledgePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset search params
    mockSearchParams.delete('ns');
  });

  it('renders the knowledge base page with global header', async () => {
    render(<KnowledgePage />);
    
    expect(screen.getByText('Knowledge Base')).toBeInTheDocument();
    expect(screen.getByText(/Manage namespaces, import documents/i)).toBeInTheDocument();
  });

  it('shows the namespaces tab by default in global view', async () => {
    render(<KnowledgePage />);
    
    // In minimal header, subViewTabs are rendered
    expect(screen.getByText('Namespaces')).toBeInTheDocument();
    expect(screen.getByText('Import')).toBeInTheDocument();
    expect(screen.getByText('Query')).toBeInTheDocument();
    
    // Should show namespace list
    expect(screen.getByText('test-namespace')).toBeInTheDocument();
    expect(screen.getByText('another-namespace')).toBeInTheDocument();
  });

  it('handles ?ns=xxx deep-linking', async () => {
    mockSearchParams.set('ns', 'test-namespace');
    render(<KnowledgePage />);
    
    // Should show "Pre-selected: test-namespace" in header
    expect(screen.getByText(/Pre-selected: test-namespace/i)).toBeInTheDocument();
    
    // Should show the selected namespace badge in the minimal header
    expect(screen.getAllByText('test-namespace').length).toBeGreaterThan(0);
  });

  it('switches between tabs', async () => {
    render(<KnowledgePage />);
    
    // Click Import
    fireEvent.click(screen.getByText('Import'));
    
    // Should show "Select a Namespace" initially in import tab if none selected
    expect(screen.getByText('Select a Namespace')).toBeInTheDocument();
    
    // Click Query
    fireEvent.click(screen.getByText('Query'));
    expect(screen.getByText('Select a Namespace')).toBeInTheDocument();
    
    // Click Namespaces back
    fireEvent.click(screen.getByText('Namespaces'));
    expect(screen.getByText('test-namespace')).toBeInTheDocument();
  });
});
