import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import McpSelector from '../components/roles/McpSelector';
import { useMcpServers } from '../hooks/use-mcp';

vi.mock('../hooks/use-mcp', () => ({
  useMcpServers: vi.fn(),
}));

const mockServers = [
  { name: 'unity-mcp', type: 'stdio' as const, status: 'active', credential_status: 'ok' as const, missing_keys: [] as string[], builtin: true, config: {} },
  { name: 'github-mcp', type: 'http' as const, status: 'active', credential_status: 'missing' as const, missing_keys: ['GITHUB_TOKEN'], builtin: false, config: {} },
  { name: 'serena-mcp', type: 'stdio' as const, status: 'inactive', credential_status: 'ok' as const, missing_keys: [] as string[], builtin: false, config: {} },
];

describe('McpSelector', () => {
  const mockOnChange = vi.fn();
  const mockUseMcpServers = useMcpServers as unknown as ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseMcpServers.mockReturnValue({
      servers: mockServers,
      isLoading: false,
      isError: undefined,
    });
  });

  it('renders with placeholder when no MCPs selected', () => {
    render(<McpSelector selectedMcpRefs={[]} onChange={mockOnChange} />);
    expect(screen.getByPlaceholderText(/search mcp/i)).toBeInTheDocument();
  });

  it('renders selected MCP server chips', () => {
    render(<McpSelector selectedMcpRefs={['unity-mcp', 'github-mcp']} onChange={mockOnChange} />);
    expect(screen.getByText('unity-mcp')).toBeInTheDocument();
    expect(screen.getByText('github-mcp')).toBeInTheDocument();
  });

  it('shows available servers in dropdown on focus', () => {
    render(<McpSelector selectedMcpRefs={[]} onChange={mockOnChange} />);
    fireEvent.focus(screen.getByPlaceholderText(/search mcp/i));

    expect(screen.getByText('unity-mcp')).toBeInTheDocument();
    expect(screen.getByText('github-mcp')).toBeInTheDocument();
    expect(screen.getByText('serena-mcp')).toBeInTheDocument();
  });

  it('displays server type badges (stdio/http) in dropdown', () => {
    render(<McpSelector selectedMcpRefs={[]} onChange={mockOnChange} />);
    fireEvent.focus(screen.getByPlaceholderText(/search mcp/i));

    const stdioBadges = screen.getAllByText('stdio');
    const httpBadges = screen.getAllByText('http');
    expect(stdioBadges.length).toBeGreaterThanOrEqual(1);
    expect(httpBadges.length).toBeGreaterThanOrEqual(1);
  });

  it('filters servers by search term', () => {
    render(<McpSelector selectedMcpRefs={[]} onChange={mockOnChange} />);
    const input = screen.getByPlaceholderText(/search mcp/i);
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'unity' } });

    expect(screen.getByText('unity-mcp')).toBeInTheDocument();
    expect(screen.queryByText('github-mcp')).not.toBeInTheDocument();
    expect(screen.queryByText('serena-mcp')).not.toBeInTheDocument();
  });

  it('calls onChange with added server on click', () => {
    render(<McpSelector selectedMcpRefs={['unity-mcp']} onChange={mockOnChange} />);
    fireEvent.focus(screen.getByPlaceholderText(/search mcp/i));
    fireEvent.click(screen.getByText('github-mcp'));

    expect(mockOnChange).toHaveBeenCalledWith(['unity-mcp', 'github-mcp']);
  });

  it('calls onChange with server removed when chip close is clicked', () => {
    render(<McpSelector selectedMcpRefs={['unity-mcp', 'github-mcp']} onChange={mockOnChange} />);

    // Each chip has a close button rendered as material icon "close"
    const closeButtons = screen.getAllByText('close');
    fireEvent.click(closeButtons[0]);

    expect(mockOnChange).toHaveBeenCalledWith(['github-mcp']);
  });

  it('excludes already-selected servers from dropdown list', () => {
    render(<McpSelector selectedMcpRefs={['unity-mcp']} onChange={mockOnChange} />);
    fireEvent.focus(screen.getByPlaceholderText(/search mcp/i));

    // Dropdown should only show github-mcp and serena-mcp (not unity-mcp)
    const dropdownButtons = screen.getAllByRole('button').filter(
      btn => btn.textContent?.includes('github-mcp') || btn.textContent?.includes('serena-mcp')
    );
    expect(dropdownButtons.length).toBe(2);
  });

  it('shows loading state while fetching servers', () => {
    mockUseMcpServers.mockReturnValue({
      servers: undefined,
      isLoading: true,
      isError: undefined,
    });

    render(<McpSelector selectedMcpRefs={[]} onChange={mockOnChange} />);
    fireEvent.focus(screen.getByPlaceholderText(/search mcp/i));

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('shows credential warning for servers with missing keys', () => {
    render(<McpSelector selectedMcpRefs={[]} onChange={mockOnChange} />);
    fireEvent.focus(screen.getByPlaceholderText(/search mcp/i));

    // github-mcp has credential_status: 'missing'
    expect(screen.getByText(/missing key/i)).toBeInTheDocument();
  });
});
