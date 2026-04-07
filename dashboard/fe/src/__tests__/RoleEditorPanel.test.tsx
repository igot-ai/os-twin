import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import RoleEditorPanel from '../components/roles/RoleEditorPanel';
import { Role } from '../types';
import { apiPost, apiPut } from '../lib/api-client';

// Mock SWR (used for /providers/api-keys)
vi.mock('swr', () => ({
  default: vi.fn(() => ({
    data: { Claude: true, GPT: false, Gemini: true },
    error: undefined,
    isLoading: false,
    mutate: vi.fn(),
  })),
  useSWRConfig: vi.fn(() => ({ mutate: vi.fn() })),
}));

// Mock hooks
vi.mock('../hooks/use-roles', () => ({
  useModelRegistry: vi.fn(() => ({
    registry: {
      claude: [{ id: 'claude-opus-4', context_window: '200k', tier: 'flagship' }],
      gemini: [{ id: 'gemini-flash', context_window: '1M', tier: 'fast' }],
    },
  })),
  useRoleDependencies: vi.fn(() => ({ dependencies: null })),
}));

// Mock api-client
vi.mock('../lib/api-client', () => ({
  apiPost: vi.fn().mockResolvedValue({ id: 'new-role', name: 'test' }),
  apiPut: vi.fn().mockResolvedValue({ id: 'existing', name: 'test' }),
}));

// Mock sub-components with minimal implementations
vi.mock('../components/roles/ProviderSelector', () => ({
  default: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <div data-testid="provider-selector">Provider: {value}</div>
  ),
}));

vi.mock('../components/roles/TestConnectionButton', () => ({
  default: () => <div data-testid="test-connection">TestConnection</div>,
}));

// Mock SkillChipInput - render with a way to verify props
vi.mock('../components/roles/SkillChipInput', () => ({
  default: ({ selectedSkillRefs, onChange }: { selectedSkillRefs: string[]; onChange: (refs: string[]) => void }) => (
    <div data-testid="skill-chip-input">
      Skills: {selectedSkillRefs.join(', ')}
    </div>
  ),
}));

// Mock McpSelector - render with a way to verify props and trigger changes
vi.mock('../components/roles/McpSelector', () => ({
  default: ({ selectedMcpRefs, onChange }: { selectedMcpRefs: string[]; onChange: (refs: string[]) => void }) => (
    <div data-testid="mcp-selector">
      MCPs: {selectedMcpRefs.join(', ')}
      <button type="button" onClick={() => onChange([...selectedMcpRefs, 'test-mcp'])}>
        add-mcp
      </button>
    </div>
  ),
}));

describe('RoleEditorPanel', () => {
  const mockOnClose = vi.fn();
  const existingRoles: Role[] = [];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all 6 configuration sections when open', () => {
    render(
      <RoleEditorPanel
        isOpen={true}
        onClose={mockOnClose}
        existingRoles={existingRoles}
      />
    );

    expect(screen.getByText('Identity & Context')).toBeInTheDocument();
    expect(screen.getByText('Model Binding')).toBeInTheDocument();
    expect(screen.getByText('Sampling Parameters')).toBeInTheDocument();
    expect(screen.getByText('Skill Matrix')).toBeInTheDocument();
    expect(screen.getByText('MCP Binding')).toBeInTheDocument();
    expect(screen.getByText('Role Instructions')).toBeInTheDocument();
  });

  it('renders McpSelector component in MCP section', () => {
    render(
      <RoleEditorPanel
        isOpen={true}
        onClose={mockOnClose}
        existingRoles={existingRoles}
      />
    );

    expect(screen.getByTestId('mcp-selector')).toBeInTheDocument();
  });

  it('initializes with empty mcp_refs for new role', () => {
    render(
      <RoleEditorPanel
        isOpen={true}
        onClose={mockOnClose}
        existingRoles={existingRoles}
      />
    );

    const mcpSelector = screen.getByTestId('mcp-selector');
    expect(mcpSelector).toHaveTextContent('MCPs:');
    // Empty mcp_refs means no server names displayed
    expect(mcpSelector.textContent).not.toContain('unity-mcp');
  });

  it('loads existing mcp_refs when editing a role', () => {
    const existingRole: Role = {
      id: 'r1',
      name: 'engineer',
      provider: 'claude',
      version: 'claude-opus-4',
      temperature: 0.3,
      budget_tokens_max: 500000,
      max_retries: 3,
      timeout_seconds: 900,
      skill_refs: ['implement-epic'],
      mcp_refs: ['unity-mcp', 'github-mcp'],
    };

    render(
      <RoleEditorPanel
        role={existingRole}
        isOpen={true}
        onClose={mockOnClose}
        existingRoles={existingRoles}
      />
    );

    const mcpSelector = screen.getByTestId('mcp-selector');
    expect(mcpSelector).toHaveTextContent('unity-mcp');
    expect(mcpSelector).toHaveTextContent('github-mcp');
  });

  it('includes mcp_refs in save payload when creating a new role', async () => {
    render(
      <RoleEditorPanel
        isOpen={true}
        onClose={mockOnClose}
        existingRoles={existingRoles}
      />
    );

    // Fill required fields
    const nameInput = screen.getByPlaceholderText(/e.g. Frontend Engineer/i);
    fireEvent.change(nameInput, { target: { value: 'test-role' } });

    // Add an MCP via mock selector
    fireEvent.click(screen.getByText('add-mcp'));

    // Click save
    fireEvent.click(screen.getByText('Create Role'));

    await waitFor(() => {
      expect(apiPost).toHaveBeenCalledWith(
        '/roles',
        expect.objectContaining({
          name: 'test-role',
          mcp_refs: ['test-mcp'],
        })
      );
    });
  });

  it('does not render when panel is closed', () => {
    render(
      <RoleEditorPanel
        isOpen={false}
        onClose={mockOnClose}
        existingRoles={existingRoles}
      />
    );

    expect(screen.queryByText('Identity & Context')).not.toBeInTheDocument();
  });

  it('displays section 05 with number badge for MCP Binding', () => {
    render(
      <RoleEditorPanel
        isOpen={true}
        onClose={mockOnClose}
        existingRoles={existingRoles}
      />
    );

    // Section numbering: 01=Identity, 02=Model, 03=Sampling, 04=Skills, 05=MCP, 06=Instructions
    expect(screen.getByText('05')).toBeInTheDocument();
    expect(screen.getByText('MCP Binding')).toBeInTheDocument();
  });
});
