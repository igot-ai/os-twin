import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import RolesTable from '../components/roles/RolesTable';
import { Role, Skill } from '../types';
import { McpServer } from '../hooks/use-mcp';

// Mock SWR (used by useSWRConfig inside RolesTable)
vi.mock('swr', () => ({
  default: vi.fn(),
  useSWRConfig: vi.fn(() => ({ mutate: vi.fn() })),
}));

// Mock useModelRegistry
vi.mock('../hooks/use-roles', () => ({
  useModelRegistry: vi.fn(() => ({
    registry: {
      Claude: [{ id: 'claude-opus-4', context_window: '200k', tier: 'flagship' }],
    },
  })),
}));

// Mock api-client
vi.mock('../lib/api-client', () => ({
  apiDelete: vi.fn(),
}));

// Mock TestConnectionButton
vi.mock('../components/roles/TestConnectionButton', () => ({
  default: () => <span>TestBtn</span>,
}));

const mockSkills: Skill[] = [
  { id: 's1', name: 'implement-epic', version: '1.0', description: 'Implement epics', category: 'implementation', applicable_roles: ['engineer'], usage_count: 10 },
  { id: 's2', name: 'code-review', version: '1.0', description: 'Review code', category: 'review', applicable_roles: ['qa'], usage_count: 5 },
];

const mockServers: McpServer[] = [
  { name: 'unity-mcp', type: 'stdio', status: 'active', credential_status: 'ok', missing_keys: [], builtin: true, config: {} },
  { name: 'github-mcp', type: 'http', status: 'active', credential_status: 'ok', missing_keys: [], builtin: false, config: {} },
  { name: 'serena-mcp', type: 'stdio', status: 'active', credential_status: 'ok', missing_keys: [], builtin: false, config: {} },
];

describe('RolesTable', () => {
  const mockOnEdit = vi.fn();
  const mockOnAdd = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders MCP column header', () => {
    const roles: Role[] = [
      { id: 'r1', name: 'engineer', provider: 'claude', version: 'claude-opus-4', temperature: 0.3, budget_tokens_max: 500000, max_retries: 3, timeout_seconds: 900, skill_refs: [], mcp_refs: [] },
    ];

    render(
      <RolesTable roles={roles} skills={mockSkills} mcpServers={mockServers} onEdit={mockOnEdit} onAdd={mockOnAdd} />
    );

    expect(screen.getByText('MCPs')).toBeInTheDocument();
  });

  it('shows MCP server names for roles with mcp_refs', () => {
    const roles: Role[] = [
      { id: 'r1', name: 'engineer', provider: 'claude', version: 'claude-opus-4', temperature: 0.3, budget_tokens_max: 500000, max_retries: 3, timeout_seconds: 900, skill_refs: ['implement-epic'], mcp_refs: ['unity-mcp', 'github-mcp'] },
    ];

    render(
      <RolesTable roles={roles} skills={mockSkills} mcpServers={mockServers} onEdit={mockOnEdit} onAdd={mockOnAdd} />
    );

    expect(screen.getByText('unity-mcp')).toBeInTheDocument();
    expect(screen.getByText('github-mcp')).toBeInTheDocument();
  });

  it('shows "No MCPs" for roles without mcp_refs', () => {
    const roles: Role[] = [
      { id: 'r1', name: 'qa', provider: 'claude', version: 'claude-opus-4', temperature: 0.2, budget_tokens_max: 300000, max_retries: 3, timeout_seconds: 600, skill_refs: [], mcp_refs: [] },
    ];

    render(
      <RolesTable roles={roles} skills={mockSkills} mcpServers={mockServers} onEdit={mockOnEdit} onAdd={mockOnAdd} />
    );

    expect(screen.getByText('No MCPs')).toBeInTheDocument();
  });

  it('truncates MCP display with "+N" when more than 2 MCPs', () => {
    const roles: Role[] = [
      { id: 'r1', name: 'engineer', provider: 'claude', version: 'claude-opus-4', temperature: 0.3, budget_tokens_max: 500000, max_retries: 3, timeout_seconds: 900, skill_refs: [], mcp_refs: ['unity-mcp', 'github-mcp', 'serena-mcp'] },
    ];

    render(
      <RolesTable roles={roles} skills={mockSkills} mcpServers={mockServers} onEdit={mockOnEdit} onAdd={mockOnAdd} />
    );

    // Should show first 2 MCPs and a "+1" badge
    expect(screen.getByText('unity-mcp')).toBeInTheDocument();
    expect(screen.getByText('github-mcp')).toBeInTheDocument();
    expect(screen.getByText('+1')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    render(
      <RolesTable roles={[]} skills={[]} mcpServers={[]} onEdit={mockOnEdit} onAdd={mockOnAdd} isLoading={true} />
    );

    expect(screen.getByText(/loading roles/i)).toBeInTheDocument();
  });

  it('renders empty state with create button', () => {
    render(
      <RolesTable roles={[]} skills={[]} mcpServers={[]} onEdit={mockOnEdit} onAdd={mockOnAdd} />
    );

    expect(screen.getByText('No Roles Configured')).toBeInTheDocument();
    expect(screen.getByText('Create First Role')).toBeInTheDocument();
  });
});
