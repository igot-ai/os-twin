/**
 * Tests for KnowledgeTab and related components.
 * Using Vitest + React Testing Library.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

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
        name: 'test-plan-id', // Plan namespace - pre-existing
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        language: 'English',
        description: 'Knowledge for plan test-plan-id',
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
    createNamespace: vi.fn().mockResolvedValue({
      schema_version: 1,
      name: 'test-plan-id',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      language: 'English',
      description: 'Knowledge for plan test-plan-id',
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
    }),
    refresh: vi.fn(),
  })),
  useKnowledgeNamespace: vi.fn(() => ({
    namespace: null,
    isLoading: false,
    isError: null,
    deleteNamespace: vi.fn(),
    refresh: vi.fn(),
  })),
}));

vi.mock('@/hooks/use-knowledge-import', () => ({
  useKnowledgeJobs: vi.fn(() => ({
    jobs: [],
    graphCounts: { entities: 0, chunks: 0, relations: 0 },
    isLoading: false,
    isError: null,
    refresh: vi.fn(),
  })),
  useKnowledgeJob: vi.fn(() => ({
    job: null,
    isLoading: false,
    isError: null,
    isTerminal: true,
    refresh: vi.fn(),
  })),
  useKnowledgeImport: vi.fn(() => ({
    startImport: vi.fn(),
  })),
  useKnowledgeImportMonitor: vi.fn(() => ({
    jobs: [],
    graphCounts: { entities: 0, chunks: 0, relations: 0 },
    activeJob: undefined,
    latestJob: undefined,
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
    graph: null,
    nodes: [],
    edges: [],
    stats: { node_count: 0, edge_count: 0 },
    error: null,
    isLoading: false,
    isError: null,
    refresh: vi.fn(),
  })),
  useKnowledgeEntity: vi.fn(() => ({
    entity: null,
    isLoading: false,
    error: null,
  })),
}));

vi.mock('@/lib/stores/notificationStore', () => ({
  useNotificationStore: vi.fn((selector) => {
    const state = { addToast: vi.fn() };
    return selector ? selector(state) : state;
  }),
}));

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  })),
  useSearchParams: vi.fn(() => new URLSearchParams()),
  usePathname: vi.fn(() => '/plans/test-plan-id'),
}));

vi.mock('@/components/plan/PlanWorkspace', () => ({
  usePlanContext: vi.fn(() => ({
    planId: 'test-plan-id',
    plan: { id: 'test-plan-id', title: 'Test Plan' },
    epics: [],
    progress: null,
    isLoading: false,
    isProgressLoading: false,
    isError: null,
    selectedEpicRef: null,
    setSelectedEpicRef: vi.fn(),
    updateEpicState: vi.fn(),
    isContextPanelOpen: false,
    setIsContextPanelOpen: vi.fn(),
    activeTab: 'knowledge',
    setActiveTab: vi.fn(),
    planContent: '',
    setPlanContent: vi.fn(),
    savePlan: vi.fn(),
    launchPlan: vi.fn(),
    reloadFromDisk: vi.fn(),
    syncStatus: undefined,
    isSaving: false,
    isLaunching: false,
    isAIChatOpen: false,
    setIsAIChatOpen: vi.fn(),
    isRefining: false,
    parsedPlan: null,
    updateParsedPlan: vi.fn(),
    undo: vi.fn(),
    redo: vi.fn(),
    canUndo: false,
    canRedo: false,
    refreshProgress: vi.fn(),
    uploadAssets: vi.fn(),
    isUploadingAssets: false,
  })),
}));

// Import after mocks
import KnowledgeTab from '@/components/plan/KnowledgeTab';
import NamespaceList from '@/components/knowledge/NamespaceList';
import ImportPanel from '@/components/knowledge/ImportPanel';
import QueryPanel from '@/components/knowledge/QueryPanel';

describe('KnowledgeTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the knowledge tab with sub-view tabs', async () => {
    render(<KnowledgeTab />);
    
    // Wait for the component to finish loading (auto-create namespace logic)
    await waitFor(() => {
      // Check header - shows "Plan Knowledge" in plan context
      expect(screen.getByText('Plan Knowledge')).toBeInTheDocument();
    });
    
    // Check sub-view tabs - in plan context, Namespaces is HIDDEN
    expect(screen.queryByText('Namespaces')).not.toBeInTheDocument();
    expect(screen.getByText('Import')).toBeInTheDocument();
    expect(screen.getByText('Query')).toBeInTheDocument();
  });

  it('displays query view by default in plan context', async () => {
    render(<KnowledgeTab />);
    
    // Wait for the component to load
    await waitFor(() => {
      expect(screen.getByText('Plan Knowledge')).toBeInTheDocument();
    });
    
    // Should show query form (default in plan context)
    expect(screen.getByPlaceholderText('Enter your query...')).toBeInTheDocument();
  });

  it('switches to Import tab when clicked', async () => {
    render(<KnowledgeTab />);
    
    // Wait for the component to load
    await waitFor(() => {
      expect(screen.getByText('Plan Knowledge')).toBeInTheDocument();
    });
    
    fireEvent.click(screen.getByText('Import'));
    
    // Since plan namespace is auto-selected, the import form is shown
    // (not "Select a Namespace" anymore)
    expect(screen.getByPlaceholderText('/absolute/path/to/folder')).toBeInTheDocument();
  });

  it('switches to Query tab when clicked', async () => {
    render(<KnowledgeTab />);
    
    // Wait for the component to load
    await waitFor(() => {
      expect(screen.getByText('Plan Knowledge')).toBeInTheDocument();
    });
    
    fireEvent.click(screen.getByText('Query'));
    
    // Since plan namespace is auto-selected, the query form is shown
    // (not "Select a Namespace" anymore)
    expect(screen.getByPlaceholderText('Enter your query...')).toBeInTheDocument();
  });
  
  it('auto-selects plan namespace and shows it in header', async () => {
    render(<KnowledgeTab />);
    
    // Wait for the component to load
    await waitFor(() => {
      expect(screen.getByText('Plan Knowledge')).toBeInTheDocument();
    });
    
    // Check that the plan namespace badge is shown in the header
    // (there are multiple elements with the namespace name, so use getAllByText)
    const namespaceElements = screen.getAllByText('test-plan-id');
    expect(namespaceElements.length).toBeGreaterThan(0);
  });
  
  it('shows View All Knowledge button in plan context', async () => {
    render(<KnowledgeTab />);
    
    // Wait for the component to load
    await waitFor(() => {
      expect(screen.getByText('Plan Knowledge')).toBeInTheDocument();
    });
    
    // Check that the View All Knowledge button is shown
    expect(screen.getByText('View All Knowledge')).toBeInTheDocument();
  });
  
  it('auto-creates namespace if it does not exist', async () => {
    const { useKnowledgeNamespaces } = await import('@/hooks/use-knowledge-namespaces');
    const mockCreateNamespace = vi.fn().mockResolvedValue({});
    
    // Mock namespaces without the plan namespace
    (useKnowledgeNamespaces as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      namespaces: [], // Empty namespaces
      isLoading: false,
      isError: null,
      createNamespace: mockCreateNamespace,
      refresh: vi.fn(),
    });
    
    render(<KnowledgeTab />);
    
    await waitFor(() => {
      expect(mockCreateNamespace).toHaveBeenCalledWith({
        name: 'test-plan-id',
        description: expect.stringContaining('test-plan-id')
      });
    });
  });
});

describe('NamespaceList', () => {
  const mockOnSelect = vi.fn();
  const mockOnCreate = vi.fn();
  const mockOnDelete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders list of namespaces', async () => {
    const namespaces = [
      {
        schema_version: 1,
        name: 'test-ns',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        language: 'English',
        description: 'Test description',
        embedding_model: 'text-embedding-3-small',
        embedding_dimension: 1536,
        stats: {
          files_indexed: 5,
          chunks: 50,
          entities: 20,
          relations: 10,
          vectors: 50,
          bytes_on_disk: 512000,
        },
        imports: [],
      },
    ];

    render(
      <NamespaceList
        namespaces={namespaces}
        selectedNamespace={null}
        onSelect={mockOnSelect}
        onCreate={mockOnCreate}
        onDelete={mockOnDelete}
        isLoading={false}
      />
    );

    expect(screen.getByText('test-ns')).toBeInTheDocument();
    expect(screen.getByText('Test description')).toBeInTheDocument();
  });

  it('shows create modal when New button clicked', async () => {
    render(
      <NamespaceList
        namespaces={[]}
        selectedNamespace={null}
        onSelect={mockOnSelect}
        onCreate={mockOnCreate}
        onDelete={mockOnDelete}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText('New'));

    expect(screen.getByText('Create Namespace')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('my-namespace')).toBeInTheDocument();
  });

  it('validates namespace name on create', async () => {
    render(
      <NamespaceList
        namespaces={[]}
        selectedNamespace={null}
        onSelect={mockOnSelect}
        onCreate={mockOnCreate}
        onDelete={mockOnDelete}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText('New'));
    
    // Enter invalid name
    fireEvent.change(screen.getByPlaceholderText('my-namespace'), { 
      target: { value: 'Invalid Name!' } 
    });
    
    fireEvent.click(screen.getByText('Create'));

    // Should show validation error
    await waitFor(() => {
      expect(screen.getByText(/must start with lowercase/i)).toBeInTheDocument();
    });
  });

  it('calls onSelect when namespace clicked', async () => {
    const namespaces = [
      {
        schema_version: 1,
        name: 'clickable-ns',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
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
    ];

    render(
      <NamespaceList
        namespaces={namespaces}
        selectedNamespace={null}
        onSelect={mockOnSelect}
        onCreate={mockOnCreate}
        onDelete={mockOnDelete}
        isLoading={false}
      />
    );

    fireEvent.click(screen.getByText('clickable-ns'));

    expect(mockOnSelect).toHaveBeenCalledWith('clickable-ns');
  });

  it('shows delete confirmation dialog when delete button clicked', async () => {
    const namespaces = [
      {
        schema_version: 1,
        name: 'deletable-ns',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        language: 'English',
        description: 'To be deleted',
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
    ];

    render(
      <NamespaceList
        namespaces={namespaces}
        selectedNamespace={null}
        onSelect={mockOnSelect}
        onCreate={mockOnCreate}
        onDelete={mockOnDelete}
        isLoading={false}
      />
    );

    // Find and click the delete button by aria-label
    const deleteButton = screen.getByRole('button', { name: /delete namespace deletable-ns/i });
    fireEvent.click(deleteButton);

    // Should show confirmation dialog
    await waitFor(() => {
      expect(screen.getByText('Delete Namespace?')).toBeInTheDocument();
    });
  });

  it('calls onDelete when delete confirmed', async () => {
    mockOnDelete.mockResolvedValueOnce(undefined);
    
    const namespaces = [
      {
        schema_version: 1,
        name: 'confirm-delete-ns',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
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
    ];

    render(
      <NamespaceList
        namespaces={namespaces}
        selectedNamespace={null}
        onSelect={mockOnSelect}
        onCreate={mockOnCreate}
        onDelete={mockOnDelete}
        isLoading={false}
      />
    );

    // Find and click the delete button
    const deleteButton = screen.getByRole('button', { name: /delete namespace confirm-delete-ns/i });
    fireEvent.click(deleteButton);

    // Wait for dialog to appear
    await waitFor(() => {
      expect(screen.getByText('Delete Namespace?')).toBeInTheDocument();
    });

    // Click the confirm delete button in the modal
    const confirmDeleteButton = screen.getByRole('button', { name: /^Delete$/i });
    fireEvent.click(confirmDeleteButton);

    // Should have called onDelete
    await waitFor(() => {
      expect(mockOnDelete).toHaveBeenCalledWith('confirm-delete-ns');
    });
  });

  it('cancels delete when Cancel clicked', async () => {
    const namespaces = [
      {
        schema_version: 1,
        name: 'cancel-delete-ns',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
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
    ];

    render(
      <NamespaceList
        namespaces={namespaces}
        selectedNamespace={null}
        onSelect={mockOnSelect}
        onCreate={mockOnCreate}
        onDelete={mockOnDelete}
        isLoading={false}
      />
    );

    // Find and click the delete button
    const deleteButton = screen.getByRole('button', { name: /delete namespace cancel-delete-ns/i });
    fireEvent.click(deleteButton);

    // Wait for dialog to appear
    await waitFor(() => {
      expect(screen.getByText('Delete Namespace?')).toBeInTheDocument();
    });

    // Click Cancel
    const cancelButton = screen.getByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelButton);

    // Should NOT have called onDelete
    expect(mockOnDelete).not.toHaveBeenCalled();
  });
});

describe('ImportPanel', () => {
  const mockOnStartImport = vi.fn();
  const mockOnRefresh = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows select namespace message when none selected', async () => {
    render(
      <ImportPanel
        selectedNamespace={null}
        jobs={[]}
        activeJob={undefined}
        isLoading={false}
        onStartImport={mockOnStartImport}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByText('Select a Namespace')).toBeInTheDocument();
  });

  it('shows import form when namespace selected', async () => {
    render(
      <ImportPanel
        selectedNamespace="test-ns"
        jobs={[]}
        activeJob={undefined}
        isLoading={false}
        onStartImport={mockOnStartImport}
        onRefresh={mockOnRefresh}
      />
    );

    expect(screen.getByPlaceholderText('/absolute/path/to/folder')).toBeInTheDocument();
    expect(screen.getByText('Import')).toBeInTheDocument();
  });

  it('shows job cards when jobs exist', async () => {
    const jobs = [
      {
        job_id: 'job-123',
        namespace: 'test-ns',
        operation: 'import',
        state: 'completed' as const,
        submitted_at: '2024-01-01T00:00:00Z',
        started_at: '2024-01-01T00:00:01Z',
        finished_at: '2024-01-01T00:01:00Z',
        progress_current: 10,
        progress_total: 10,
        message: 'Import completed successfully',
        errors: [],
        result: null,
      },
    ];

    render(
      <ImportPanel
        selectedNamespace="test-ns"
        jobs={jobs}
        activeJob={undefined}
        isLoading={false}
        onStartImport={mockOnStartImport}
        onRefresh={mockOnRefresh}
      />
    );

    // Check for the message in the job card
    expect(screen.getByText('Import completed successfully')).toBeInTheDocument();
  });

  it('disables import button when job is running', async () => {
    const runningJob = {
      job_id: 'job-456',
      namespace: 'test-ns',
      operation: 'import',
      state: 'running' as const,
      submitted_at: '2024-01-01T00:00:00Z',
      started_at: '2024-01-01T00:00:01Z',
      finished_at: null,
      progress_current: 5,
      progress_total: 10,
      message: 'Importing...',
      errors: [],
      result: null,
    };

    render(
      <ImportPanel
        selectedNamespace="test-ns"
        jobs={[runningJob]}
        activeJob={runningJob}
        isLoading={false}
        onStartImport={mockOnStartImport}
        onRefresh={mockOnRefresh}
      />
    );

    // Import button should be disabled
    const importButton = screen.getByText('Import');
    expect(importButton).toBeDisabled();
  });
});

describe('QueryPanel', () => {
  const mockOnExecuteQuery = vi.fn();
  const mockOnClearResult = vi.fn();
  const mockOnRefreshGraph = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows select namespace message when none selected', async () => {
    render(
      <QueryPanel
        selectedNamespace={null}
        queryResult={null}
        isLoading={false}
        error={null}
        graphNodes={[]}
        graphEdges={[]}
        graphStats={{ node_count: 0, edge_count: 0 }}
        graphLoading={false}
        onExecuteQuery={mockOnExecuteQuery}
        onClearResult={mockOnClearResult}
        onRefreshGraph={mockOnRefreshGraph}
      />
    );

    expect(screen.getByText('Select a Namespace')).toBeInTheDocument();
  });

  it('shows query form when namespace selected', async () => {
    render(
      <QueryPanel
        selectedNamespace="test-ns"
        queryResult={null}
        isLoading={false}
        error={null}
        graphNodes={[]}
        graphEdges={[]}
        graphStats={{ node_count: 0, edge_count: 0 }}
        graphLoading={false}
        onExecuteQuery={mockOnExecuteQuery}
        onClearResult={mockOnClearResult}
        onRefreshGraph={mockOnRefreshGraph}
      />
    );

    expect(screen.getByPlaceholderText('Enter your query...')).toBeInTheDocument();
    expect(screen.getByText('Search')).toBeInTheDocument();
  });

  it('renders query result with chunks', async () => {
    const result = {
      query: 'test query',
      mode: 'raw',
      namespace: 'test-ns',
      chunks: [
        {
          text: 'This is a test chunk of text.',
          score: 0.95,
          file_path: '/test/file.txt',
          filename: 'file.txt',
          chunk_index: 0,
          total_chunks: 1,
          file_hash: 'abc123',
          mime_type: 'text/plain',
          category_id: null,
          memory_links: [],
        },
      ],
      entities: [],
      answer: null,
      citations: [],
      latency_ms: 150,
      warnings: [],
    };

    render(
      <QueryPanel
        selectedNamespace="test-ns"
        queryResult={result}
        isLoading={false}
        error={null}
        graphNodes={[]}
        graphEdges={[]}
        graphStats={{ node_count: 0, edge_count: 0 }}
        graphLoading={false}
        onExecuteQuery={mockOnExecuteQuery}
        onClearResult={mockOnClearResult}
        onRefreshGraph={mockOnRefreshGraph}
      />
    );

    expect(screen.getByText('Relevant Chunks (1)')).toBeInTheDocument();
    expect(screen.getByText('This is a test chunk of text.')).toBeInTheDocument();
  });

  it('renders query result with entities', async () => {
    const result = {
      query: 'test query',
      mode: 'graph',
      namespace: 'test-ns',
      chunks: [],
      entities: [
        {
          id: 'ent-1',
          name: 'Test Entity',
          label: 'person',
          score: 0.8,
          description: 'A test entity',
          category_id: null,
        },
      ],
      answer: null,
      citations: [],
      latency_ms: 200,
      warnings: [],
    };

    render(
      <QueryPanel
        selectedNamespace="test-ns"
        queryResult={result}
        isLoading={false}
        error={null}
        graphNodes={[]}
        graphEdges={[]}
        graphStats={{ node_count: 0, edge_count: 0 }}
        graphLoading={false}
        onExecuteQuery={mockOnExecuteQuery}
        onClearResult={mockOnClearResult}
        onRefreshGraph={mockOnRefreshGraph}
      />
    );

    expect(screen.getByText('Entities (1)')).toBeInTheDocument();
    expect(screen.getByText('Test Entity')).toBeInTheDocument();
  });

  it('shows LLM unavailable warning for summarized mode', async () => {
    const result = {
      query: 'test query',
      mode: 'summarized',
      namespace: 'test-ns',
      chunks: [],
      entities: [],
      answer: null,
      citations: [],
      latency_ms: 100,
      warnings: ['llm_unavailable'],
    };

    render(
      <QueryPanel
        selectedNamespace="test-ns"
        queryResult={result}
        isLoading={false}
        error={null}
        graphNodes={[]}
        graphEdges={[]}
        graphStats={{ node_count: 0, edge_count: 0 }}
        graphLoading={false}
        onExecuteQuery={mockOnExecuteQuery}
        onClearResult={mockOnClearResult}
        onRefreshGraph={mockOnRefreshGraph}
      />
    );

    // Change mode to summarized
    const modeSelect = screen.getByRole('combobox');
    fireEvent.change(modeSelect, { target: { value: 'summarized' } });

    // Now the warning should appear
    await waitFor(() => {
      expect(screen.getByText('LLM Not Configured')).toBeInTheDocument();
    });
  });

  it('renders empty state when no graph nodes', async () => {
    render(
      <QueryPanel
        selectedNamespace="test-ns"
        queryResult={null}
        isLoading={false}
        error={null}
        graphNodes={[]}
        graphEdges={[]}
        graphStats={{ node_count: 0, edge_count: 0 }}
        graphLoading={false}
        onExecuteQuery={mockOnExecuteQuery}
        onClearResult={mockOnClearResult}
        onRefreshGraph={mockOnRefreshGraph}
      />
    );

    expect(screen.getByText('No entities yet')).toBeInTheDocument();
  });

  it('renders graph with nodes', async () => {
    const nodes = [
      {
        id: 'node-1',
        label: 'person',
        name: 'John Doe',
        score: 1.0,
        properties: {},
      },
      {
        id: 'node-2',
        label: 'organization',
        name: 'Acme Corp',
        score: 0.9,
        properties: {},
      },
    ];

    const edges = [
      {
        source: 'node-1',
        target: 'node-2',
        label: 'WORKS_FOR',
      },
    ];

    render(
      <QueryPanel
        selectedNamespace="test-ns"
        queryResult={null}
        isLoading={false}
        error={null}
        graphNodes={nodes}
        graphEdges={edges}
        graphStats={{ node_count: 2, edge_count: 1 }}
        graphLoading={false}
        onExecuteQuery={mockOnExecuteQuery}
        onClearResult={mockOnClearResult}
        onRefreshGraph={mockOnRefreshGraph}
      />
    );

    // Should show stats badge in the graph panel
    expect(screen.getByText('2 nodes · 1 edges')).toBeInTheDocument();
  });
});
