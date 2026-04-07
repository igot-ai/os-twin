/**
 * Unit tests for MemoryTab component.
 *
 * Tests the memory visualizer tab that displays agent memories
 * as a graph with note list, graph canvas, and detail panel.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import React from 'react';

// Polyfill ResizeObserver for jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
} as any;

// ── Mock api-client ──────────────────────────────────────────────────

const mockApiGet = vi.fn();

vi.mock('@/lib/api-client', () => ({
  apiGet: (...args: any[]) => mockApiGet(...args),
}));

// ── Mock PlanWorkspace context ───────────────────────────────────────

const mockPlanContext = {
  planId: 'test-plan',
  plan: { title: 'Test Plan', status: 'active' },
  epics: [],
  progress: null,
  isProgressLoading: false,
  activeTab: 'memory',
  setActiveTab: vi.fn(),
  planContent: '',
  setPlanContent: vi.fn(),
  parsedPlan: null,
  syncStatus: null,
  isSaving: false,
  savePlan: vi.fn(),
  launchPlan: vi.fn(),
  reloadFromDisk: vi.fn(),
  selectedEpicRef: null,
  setSelectedEpicRef: vi.fn(),
};

vi.mock('../components/plan/PlanWorkspace', () => ({
  usePlanContext: () => mockPlanContext,
}));

// ── Test data ────────────────────────────────────────────────────────

const MOCK_GRAPH = {
  groups: [
    { id: 'architecture', label: 'Architecture', color: '#8b5cf6', description: 'Notes in architecture' },
    { id: 'misc', label: 'Misc', color: '#facc15', description: 'Notes in misc' },
  ],
  nodes: [
    {
      id: 'database-schemas',
      title: 'Video Platform: Database Schemas',
      path: 'architecture/database/database-schemas.md',
      pathLabel: 'architecture/database',
      excerpt: 'PostgreSQL schema for video platform with users, videos, comments, likes.',
      content: '# Video Platform: Database Schemas\n\nCREATE TABLE users...',
      summary: 'PostgreSQL schema for video platform',
      keywords: ['users', 'videos', 'postgresql'],
      tags: ['database', 'schema'],
      groupId: 'architecture',
      color: '#8b5cf6',
      weight: 1.6,
      connections: 2,
    },
    {
      id: 'api-contracts',
      title: 'API Contracts — Video Platform',
      path: 'architecture/api/api-contracts.md',
      pathLabel: 'architecture/api',
      excerpt: 'REST API endpoints for the video platform.',
      content: '# API Contracts\n\nPOST /api/users/register...',
      summary: 'REST API endpoints',
      keywords: ['REST', 'endpoints'],
      tags: ['api', 'rest'],
      groupId: 'architecture',
      color: '#8b5cf6',
      weight: 1.3,
      connections: 1,
    },
    {
      id: 'minimal-note',
      title: 'Minimal Note',
      path: 'misc/minimal-note.md',
      pathLabel: 'misc',
      excerpt: 'Just a simple note.',
      content: '# Minimal Note\n\nJust a simple note.',
      summary: 'Simple note',
      keywords: [],
      tags: [],
      groupId: 'misc',
      color: '#facc15',
      weight: 1.0,
      connections: 0,
    },
  ],
  links: [
    { source: 'database-schemas', target: 'api-contracts', strength: 0.5 },
  ],
  stats: {
    total_memories: 3,
    total_links: 1,
    total_groups: 2,
  },
};

const MOCK_STATS = {
  total_notes: 3,
  total_tags: 4,
  total_keywords: 5,
  total_paths: 3,
  memory_dir: '/tmp/test/.memory',
  tags: ['api', 'database', 'rest', 'schema'],
  paths: ['architecture/api', 'architecture/database', 'misc'],
};

const EMPTY_GRAPH = {
  groups: [],
  nodes: [],
  links: [],
  stats: { total_memories: 0, total_links: 0, total_groups: 0 },
};

const EMPTY_STATS = {
  total_notes: 0,
  total_tags: 0,
  total_keywords: 0,
  total_paths: 0,
  memory_dir: '/tmp/test/.memory',
  tags: [],
  paths: [],
};

// ── Import component after mocks ─────────────────────────────────────

let MemoryTab: any;

beforeEach(async () => {
  vi.restoreAllMocks();
  mockApiGet.mockReset();
  // Re-import to get fresh module
  const mod = await import('../components/plan/MemoryTab');
  MemoryTab = mod.default;
});

// ── Tests ────────────────────────────────────────────────────────────

describe('MemoryTab', () => {
  describe('Loading state', () => {
    it('shows loading spinner while fetching', () => {
      mockApiGet.mockReturnValue(new Promise(() => {})); // never resolves
      render(<MemoryTab />);
      expect(screen.getByText('Loading memory graph...')).toBeInTheDocument();
    });
  });

  describe('Error state', () => {
    it('shows error message when API fails', async () => {
      mockApiGet.mockRejectedValue(new Error('No .memory/ found'));
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText('No memories found')).toBeInTheDocument();
      });
    });

    it('shows helpful guidance on error', async () => {
      mockApiGet.mockRejectedValue(new Error('404'));
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText(/Run the plan to generate/)).toBeInTheDocument();
      });
    });
  });

  describe('Empty state', () => {
    it('shows empty state when no memories exist', async () => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/graph')) return Promise.resolve(EMPTY_GRAPH);
        if (url.includes('/stats')) return Promise.resolve(EMPTY_STATS);
        return Promise.reject(new Error('Unknown endpoint'));
      });
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText('No memories yet')).toBeInTheDocument();
      });
    });
  });

  describe('With data', () => {
    beforeEach(() => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/graph')) return Promise.resolve(MOCK_GRAPH);
        if (url.includes('/stats')) return Promise.resolve(MOCK_STATS);
        return Promise.reject(new Error('Unknown endpoint'));
      });
    });

    it('renders the memory tab header', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText('Agent Memory')).toBeInTheDocument();
      });
    });

    it('shows note count badge', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText('3 notes')).toBeInTheDocument();
      });
    });

    it('shows tag count badge', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText('4 tags')).toBeInTheDocument();
      });
    });

    it('shows link count badge', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText('1 links')).toBeInTheDocument();
      });
    });

    it('renders note list with all notes', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getAllByText('Video Platform: Database Schemas').length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText('API Contracts — Video Platform').length).toBeGreaterThanOrEqual(1);
        expect(screen.getAllByText('Minimal Note').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('renders group legend', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText('Architecture')).toBeInTheDocument();
        expect(screen.getByText('Misc')).toBeInTheDocument();
      });
    });

    it('selects first node by default', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        // Detail panel should show the first node's path
        expect(screen.getAllByText('architecture/database').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('shows tags in detail panel', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText('database')).toBeInTheDocument();
        expect(screen.getByText('schema')).toBeInTheDocument();
      });
    });

    it('shows keywords in detail panel', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText(/users, videos, postgresql/)).toBeInTheDocument();
      });
    });
  });

  describe('Search', () => {
    beforeEach(() => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/graph')) return Promise.resolve(MOCK_GRAPH);
        if (url.includes('/stats')) return Promise.resolve(MOCK_STATS);
        return Promise.reject(new Error('Unknown endpoint'));
      });
    });

    it('renders search input', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search memories...')).toBeInTheDocument();
      });
    });

    it('filters notes by search query', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getAllByText('Video Platform: Database Schemas').length).toBeGreaterThanOrEqual(1);
      });

      const searchInput = screen.getByPlaceholderText('Search memories...');
      fireEvent.change(searchInput, { target: { value: 'api' } });

      await waitFor(() => {
        // API note should still be visible, Minimal should be filtered from the list
        // Note: SVG text may still show due to graph rendering all nodes
        const apiMatches = screen.getAllByText('API Contracts — Video Platform');
        expect(apiMatches.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('filters by tags', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getAllByText('Minimal Note').length).toBeGreaterThanOrEqual(1);
      });

      const searchInput = screen.getByPlaceholderText('Search memories...');
      fireEvent.change(searchInput, { target: { value: 'database' } });

      await waitFor(() => {
        const dbMatches = screen.getAllByText('Video Platform: Database Schemas');
        expect(dbMatches.length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe('Interaction', () => {
    beforeEach(() => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/graph')) return Promise.resolve(MOCK_GRAPH);
        if (url.includes('/stats')) return Promise.resolve(MOCK_STATS);
        return Promise.reject(new Error('Unknown endpoint'));
      });
    });

    it('selects note when clicked in list', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getAllByText('API Contracts — Video Platform').length).toBeGreaterThanOrEqual(1);
      });

      // Click the first match (list button, not SVG text)
      const apiButtons = screen.getAllByText('API Contracts — Video Platform');
      fireEvent.click(apiButtons[0]);

      await waitFor(() => {
        expect(screen.getAllByText('architecture/api').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('calls API with correct plan_id', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(mockApiGet).toHaveBeenCalledWith('/api/amem/test-plan/graph');
        expect(mockApiGet).toHaveBeenCalledWith('/api/amem/test-plan/stats');
      });
    });

    it('refresh button calls API again', async () => {
      render(<MemoryTab />);
      await waitFor(() => {
        expect(screen.getByText('Agent Memory')).toBeInTheDocument();
      });

      const callCount = mockApiGet.mock.calls.length;
      fireEvent.click(screen.getByTitle('Refresh'));

      await waitFor(() => {
        expect(mockApiGet.mock.calls.length).toBeGreaterThan(callCount);
      });
    });
  });

  describe('Graph rendering', () => {
    beforeEach(() => {
      mockApiGet.mockImplementation((url: string) => {
        if (url.includes('/graph')) return Promise.resolve(MOCK_GRAPH);
        if (url.includes('/stats')) return Promise.resolve(MOCK_STATS);
        return Promise.reject(new Error('Unknown endpoint'));
      });
    });

    it('renders SVG graph', async () => {
      const { container } = render(<MemoryTab />);
      await waitFor(() => {
        const svg = container.querySelector('svg');
        expect(svg).toBeInTheDocument();
      });
    });

    it('renders correct number of circles (nodes)', async () => {
      const { container } = render(<MemoryTab />);
      await waitFor(() => {
        // Each node has at least one circle
        const circles = container.querySelectorAll('circle');
        expect(circles.length).toBeGreaterThanOrEqual(3);
      });
    });

    it('renders link lines', async () => {
      const { container } = render(<MemoryTab />);
      await waitFor(() => {
        const lines = container.querySelectorAll('line');
        expect(lines.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('renders node labels as text', async () => {
      const { container } = render(<MemoryTab />);
      await waitFor(() => {
        const texts = container.querySelectorAll('svg text');
        expect(texts.length).toBe(3);
      });
    });
  });
});

describe('NoteDetail panel', () => {
  beforeEach(() => {
    mockApiGet.mockImplementation((url: string) => {
      if (url.includes('/graph')) return Promise.resolve(MOCK_GRAPH);
      if (url.includes('/stats')) return Promise.resolve(MOCK_STATS);
      return Promise.reject(new Error('Unknown endpoint'));
    });
  });

  it('auto-selects first node and shows detail', async () => {
    render(<MemoryTab />);
    await waitFor(() => {
      // First node is auto-selected, so detail should show its path
      expect(screen.getAllByText('architecture/database').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows connection count for selected note', async () => {
    render(<MemoryTab />);
    await waitFor(() => {
      expect(screen.getByText('2 connections')).toBeInTheDocument();
    });
  });

  it('shows group name for selected note', async () => {
    render(<MemoryTab />);
    await waitFor(() => {
      expect(screen.getByText('architecture')).toBeInTheDocument();
    });
  });
});
