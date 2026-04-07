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
  { name: 'unity-mcp', type: 'stdio' as const, status: 'active', credential_status: 'ok' as const, missing_keys: [] as string[], builtin: true, config: { command: ['node', 'unity-mcp-server'] } },
  { name: 'github-mcp', type: 'http' as const, status: 'active', credential_status: 'missing' as const, missing_keys: ['GITHUB_TOKEN'], builtin: false, config: { url: 'https://mcp.github.com' } },
  { name: 'serena-mcp', type: 'stdio' as const, status: 'inactive', credential_status: 'ok' as const, missing_keys: [] as string[], builtin: false, config: { command: ['serena'] } },
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
    // When items are selected, placeholder is empty - use getByRole instead
    fireEvent.focus(screen.getByRole('textbox'));
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
    // When items are selected, placeholder is empty - use getByRole instead
    fireEvent.focus(screen.getByRole('textbox'));

    // Dropdown should only show github-mcp and serena-mcp (not unity-mcp)
    const dropdownButtons = screen.getAllByRole('button').filter(
      (btn: HTMLElement) => btn.textContent?.includes('github-mcp') || btn.textContent?.includes('serena-mcp')
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

describe('McpSelector - enhanced chip metadata', () => {
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

  it('shows status indicator dot on selected chips', () => {
    const { container } = render(
      <McpSelector selectedMcpRefs={['unity-mcp', 'serena-mcp']} onChange={mockOnChange} />
    );

    // unity-mcp is active (green dot), serena-mcp is inactive (grey dot)
    const greenDots = container.querySelectorAll('.bg-emerald-500');
    const greyDots = container.querySelectorAll('.bg-slate-300');
    expect(greenDots.length).toBeGreaterThanOrEqual(1);
    expect(greyDots.length).toBeGreaterThanOrEqual(1);
  });

  it('shows credential warning icon on selected chips with missing keys', () => {
    render(<McpSelector selectedMcpRefs={['github-mcp']} onChange={mockOnChange} />);

    // github-mcp has credential_status: 'missing' - should show warning on the chip
    expect(screen.getByText('warning')).toBeInTheDocument();
  });

  it('shows config detail (command or url) on selected chips', () => {
    render(<McpSelector selectedMcpRefs={['unity-mcp', 'github-mcp']} onChange={mockOnChange} />);

    // unity-mcp has config.command, github-mcp has config.url
    // Should show a shortened config hint
    expect(screen.getByText(/unity-mcp-server/i)).toBeInTheDocument();
    expect(screen.getByText(/mcp\.github\.com/i)).toBeInTheDocument();
  });
});
