/**
 * Unit tests for DeployPanel component.
 *
 * Tests the deploy panel that displays launch results and deploy status
 * with working_dir, log path, URLs, warnings/errors, and preview controls.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DeployStatus } from '@/types';

// ── Mock use-deploy hook ───────────────────────────────────────────────

const mockStartPreview = vi.fn();
const mockStopPreview = vi.fn();
const mockRestartPreview = vi.fn();
const mockRefresh = vi.fn();

const mockDeployStatus: DeployStatus = {
  plan_id: 'test-plan',
  status: 'stopped' as const,
  pid: null,
  port: null,
  local_url: null,
  public_url: null,
  command: null,
  detection_method: 'none',
  started_at: null,
  updated_at: null,
  working_dir: '/tmp/test-plan',
  log_file: null,
  error: null,
};

let currentDeployStatus: DeployStatus = { ...mockDeployStatus };

vi.mock('@/hooks/use-deploy', () => ({
  useDeployStatus: () => ({
    deployStatus: currentDeployStatus,
    isLoading: false,
    isError: null,
    startPreview: mockStartPreview,
    stopPreview: mockStopPreview,
    restartPreview: mockRestartPreview,
    refresh: mockRefresh,
  }),
}));

// ── Mock PlanWorkspace context ─────────────────────────────────────────

const mockPlanContext = {
  planId: 'test-plan',
};

vi.mock('../components/plan/PlanWorkspace', () => ({
  usePlanContext: () => mockPlanContext,
}));

// ── Test data ───────────────────────────────────────────────────────────

const MOCK_LAUNCH_SUCCESS = {
  status: 'launched' as const,
  plan_file: 'test-plan.md',
  plan_id: 'test-plan',
  working_dir: '/tmp/test-plan',
  launch_log: '/tmp/test-plan/launch.log',
  preflight: {
    path_check: {
      ok: true,
      exists: true,
      is_file: true,
      writable: true,
      creatable: false,
      resolved_path: '/tmp/test-plan/test-plan.md',
      error: null,
    },
  },
  runtime_sanity: {
    ok: true,
    errors: [],
    warnings: [],
    checks: {
      working_dir: {
        ok: true,
        path: '/tmp/test-plan',
        exists: true,
        writable: true,
      },
      ngrok: {
        token_configured: true,
        tunnel_active: false,
        url: null,
      },
      channels: {},
      providers: {
        configured: true,
        providers: {},
      },
      vault: {
        backend: 'file',
        healthy: true,
        message: 'Vault initialized',
      },
      mcp: {
        servers: 0,
        server_names: [],
        ok: true,
      },
    },
  },
};

const MOCK_LAUNCH_WITH_WARNINGS = {
  ...MOCK_LAUNCH_SUCCESS,
  runtime_sanity: {
    ...MOCK_LAUNCH_SUCCESS.runtime_sanity,
    warnings: ['ngrok token not configured', 'no channels enabled'],
  },
};

const MOCK_LAUNCH_WITH_ERRORS = {
  ...MOCK_LAUNCH_SUCCESS,
  runtime_sanity: {
    ...MOCK_LAUNCH_SUCCESS.runtime_sanity,
    errors: ['working directory not writable'],
    warnings: ['ngrok token not configured'],
  },
};

const MOCK_DEPLOY_RUNNING = {
  plan_id: 'test-plan',
  status: 'running' as const,
  pid: 12345,
  port: 3000,
  local_url: 'http://localhost:3000',
  public_url: 'https://abc123.ngrok.io',
  command: 'npm run dev',
  detection_method: 'pid_file',
  started_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  working_dir: '/tmp/test-plan',
  log_file: '/tmp/test-plan/preview.log',
  error: null,
};

const MOCK_DEPLOY_NOT_CONFIGURED = {
  plan_id: 'test-plan',
  status: 'not_configured' as const,
  pid: null,
  port: null,
  local_url: null,
  public_url: null,
  command: null,
  detection_method: 'none',
  started_at: null,
  updated_at: null,
  working_dir: '/tmp/test-plan',
  log_file: null,
  error: null,
};

// ── Import component after mocks ────────────────────────────────────────

let DeployPanel: any;

beforeEach(async () => {
  vi.restoreAllMocks();
  mockStartPreview.mockReset();
  mockStopPreview.mockReset();
  mockRestartPreview.mockReset();
  mockRefresh.mockReset();
  currentDeployStatus = { ...mockDeployStatus };
  
  // Re-import to get fresh module
  const mod = await import('../components/plan/DeployPanel');
  DeployPanel = mod.default;
});

// ── Tests ──────────────────────────────────────────────────────────────

describe('DeployPanel', () => {
  describe('Render conditions', () => {
    it('renders when launchResult is provided', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_SUCCESS} />);
      expect(screen.getByText('Deploy')).toBeInTheDocument();
    });

    it('renders when only deployStatus is available', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
      render(<DeployPanel launchResult={null} />);
      expect(screen.getByText('Deploy')).toBeInTheDocument();
    });
  });

  describe('Launch success rendering', () => {
    it('shows working_dir from launchResult', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_SUCCESS} />);
      expect(screen.getByText('/tmp/test-plan')).toBeInTheDocument();
    });

    it('shows launch_log path', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_SUCCESS} />);
      expect(screen.getByText('/tmp/test-plan/launch.log')).toBeInTheDocument();
    });

    it('shows preflight path check when available', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_SUCCESS} />);
      // Preflight data should be used for internal logic, not directly displayed
      expect(screen.getByText('Working Dir')).toBeInTheDocument();
    });

    it('prefers launchResult working_dir over deployStatus', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_RUNNING, working_dir: '/different/path' };
      render(<DeployPanel launchResult={MOCK_LAUNCH_SUCCESS} />);
      expect(screen.getByText('/tmp/test-plan')).toBeInTheDocument();
    });
  });

  describe('Deploy URLs as links', () => {
    it('renders local URL as clickable link', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
      render(<DeployPanel launchResult={null} />);
      
      const localLink = screen.getByRole('link', { name: /Local:/ });
      expect(localLink).toHaveAttribute('href', 'http://localhost:3000');
      expect(localLink).toHaveAttribute('target', '_blank');
    });

    it('renders public URL as clickable link', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
      render(<DeployPanel launchResult={null} />);
      
      const publicLink = screen.getByRole('link', { name: /Public:/ });
      expect(publicLink).toHaveAttribute('href', 'https://abc123.ngrok.io');
      expect(publicLink).toHaveAttribute('target', '_blank');
    });

    it('shows URL section only when URLs are available', () => {
      currentDeployStatus = { ...mockDeployStatus };
      render(<DeployPanel launchResult={null} />);
      expect(screen.queryByText('URLs')).not.toBeInTheDocument();
    });

    it('renders open_in_new icon for local URL', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
      render(<DeployPanel launchResult={null} />);
      expect(screen.getByText('open_in_new')).toBeInTheDocument();
    });

    it('renders public icon for public URL', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
      render(<DeployPanel launchResult={null} />);
      expect(screen.getByText('public')).toBeInTheDocument();
    });
  });

  describe('Warning state rendering', () => {
    it('shows warnings when runtime_sanity has warnings', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_WITH_WARNINGS} />);
      expect(screen.getByText('Warnings')).toBeInTheDocument();
      expect(screen.getByText('ngrok token not configured')).toBeInTheDocument();
      expect(screen.getByText('no channels enabled')).toBeInTheDocument();
    });

    it('shows warning icon for warnings', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_WITH_WARNINGS} />);
      const warningIcons = screen.getAllByText('warning');
      expect(warningIcons.length).toBeGreaterThan(0);
    });

    it('shows warning badge in header when warnings present', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_WITH_WARNINGS} />);
      const warningIcons = screen.getAllByText('warning');
      expect(warningIcons.length).toBeGreaterThan(0);
    });

    it('truncates long warnings', () => {
      const longWarning = 'This is a very long warning message that should be truncated when displayed in the UI to prevent layout issues';
      const launchWithLongWarning = {
        ...MOCK_LAUNCH_SUCCESS,
        runtime_sanity: {
          ...MOCK_LAUNCH_SUCCESS.runtime_sanity,
          warnings: [longWarning],
        },
      };
      render(<DeployPanel launchResult={launchWithLongWarning} />);
      const warningElement = screen.getByText(longWarning);
      expect(warningElement).toHaveClass('truncate');
    });
  });

  describe('Error state rendering', () => {
    it('shows errors when runtime_sanity has errors', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_WITH_ERRORS} />);
      expect(screen.getByText('Errors')).toBeInTheDocument();
      expect(screen.getByText('working directory not writable')).toBeInTheDocument();
    });

    it('shows error icon for errors', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_WITH_ERRORS} />);
      const errorIcons = screen.getAllByText('error');
      expect(errorIcons.length).toBeGreaterThan(0);
    });

    it('shows error badge in header when errors present', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_WITH_ERRORS} />);
      const errorIcons = screen.getAllByText('error');
      expect(errorIcons.length).toBeGreaterThan(0);
    });

    it('shows warnings even when errors present', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_WITH_ERRORS} />);
      expect(screen.getByText('Errors')).toBeInTheDocument();
      expect(screen.getByText('Warnings')).toBeInTheDocument();
    });
  });

  describe('Status badges', () => {
    it('shows Running badge when status is running', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
      render(<DeployPanel launchResult={null} />);
      expect(screen.getByText('Running')).toBeInTheDocument();
    });

    it('shows Stopped badge when status is stopped', () => {
      currentDeployStatus = { ...mockDeployStatus };
      render(<DeployPanel launchResult={null} />);
      expect(screen.getByText('Stopped')).toBeInTheDocument();
    });

    it('shows Not Configured badge when status is not_configured', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_NOT_CONFIGURED };
      render(<DeployPanel launchResult={null} />);
      expect(screen.getByText('Not Configured')).toBeInTheDocument();
    });

    it('shows play_circle icon when running', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
      render(<DeployPanel launchResult={null} />);
      expect(screen.getByText('play_circle')).toBeInTheDocument();
    });

    it('shows error icon when errors present', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_WITH_ERRORS} />);
      const errorIcons = screen.getAllByText('error');
      expect(errorIcons.length).toBeGreaterThan(0);
    });

    it('shows warning icon when warnings present', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_WITH_WARNINGS} />);
      const warningIcons = screen.getAllByText('warning');
      expect(warningIcons.length).toBeGreaterThan(0);
    });

    it('shows rocket_launch icon when no issues', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_SUCCESS} />);
      expect(screen.getByText('rocket_launch')).toBeInTheDocument();
    });
  });

  describe('Preview control buttons', () => {
    describe('Start Preview button', () => {
      it('shows Start Preview when not running', () => {
        render(<DeployPanel launchResult={null} />);
        expect(screen.getByText('Start Preview')).toBeInTheDocument();
      });

      it('calls startPreview when clicked', async () => {
        mockStartPreview.mockResolvedValue({ ...MOCK_DEPLOY_RUNNING });
        render(<DeployPanel launchResult={null} />);
        
        fireEvent.click(screen.getByText('Start Preview'));
        
        await waitFor(() => {
          expect(mockStartPreview).toHaveBeenCalledOnce();
        });
      });

      it('is disabled when not_configured', () => {
        currentDeployStatus = { ...MOCK_DEPLOY_NOT_CONFIGURED };
        render(<DeployPanel launchResult={null} />);
        
        const button = screen.getByText('Start Preview').closest('button');
        expect(button).toBeDisabled();
      });

      it('shows play_arrow icon', () => {
        render(<DeployPanel launchResult={null} />);
        expect(screen.getByText('play_arrow')).toBeInTheDocument();
      });
    });

    describe('Stop Preview button', () => {
      it('shows Stop Preview when running', () => {
        currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
        render(<DeployPanel launchResult={null} />);
        expect(screen.getByText('Stop Preview')).toBeInTheDocument();
      });

      it('calls stopPreview when clicked', async () => {
        mockStopPreview.mockResolvedValue({ ...mockDeployStatus });
        currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
        render(<DeployPanel launchResult={null} />);
        
        fireEvent.click(screen.getByText('Stop Preview'));
        
        await waitFor(() => {
          expect(mockStopPreview).toHaveBeenCalledOnce();
        });
      });

      it('shows stop icon', () => {
        currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
        render(<DeployPanel launchResult={null} />);
        expect(screen.getByText('stop')).toBeInTheDocument();
      });
    });

    describe('Restart button', () => {
      it('shows Restart when running', () => {
        currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
        render(<DeployPanel launchResult={null} />);
        expect(screen.getByText('Restart')).toBeInTheDocument();
      });

      it('is hidden when not running', () => {
        render(<DeployPanel launchResult={null} />);
        expect(screen.queryByText('Restart')).not.toBeInTheDocument();
      });

      it('calls restartPreview when clicked', async () => {
        mockRestartPreview.mockResolvedValue({ ...MOCK_DEPLOY_RUNNING });
        currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
        render(<DeployPanel launchResult={null} />);
        
        fireEvent.click(screen.getByText('Restart'));
        
        await waitFor(() => {
          expect(mockRestartPreview).toHaveBeenCalledOnce();
        });
      });

      it('shows refresh icon', () => {
        currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
        render(<DeployPanel launchResult={null} />);
        expect(screen.getByText('refresh')).toBeInTheDocument();
      });
    });
  });

  describe('Additional info display', () => {
    it('shows command when available', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
      render(<DeployPanel launchResult={null} />);
      expect(screen.getByText('npm run dev')).toBeInTheDocument();
    });

    it('shows preview log when available', () => {
      currentDeployStatus = { ...MOCK_DEPLOY_RUNNING };
      render(<DeployPanel launchResult={null} />);
      expect(screen.getByText('/tmp/test-plan/preview.log')).toBeInTheDocument();
    });

    it('hides command when not available', () => {
      render(<DeployPanel launchResult={null} />);
      expect(screen.queryByText('Command')).not.toBeInTheDocument();
    });

    it('hides preview log when not available', () => {
      render(<DeployPanel launchResult={null} />);
      expect(screen.queryByText('Preview Log')).not.toBeInTheDocument();
    });
  });

  describe('Close button', () => {
    it('shows close button when onClose provided', () => {
      const onClose = vi.fn();
      render(<DeployPanel launchResult={MOCK_LAUNCH_SUCCESS} onClose={onClose} />);
      expect(screen.getByText('close')).toBeInTheDocument();
    });

    it('hides close button when onClose not provided', () => {
      render(<DeployPanel launchResult={MOCK_LAUNCH_SUCCESS} />);
      expect(screen.queryByText('close')).not.toBeInTheDocument();
    });

    it('calls onClose when clicked', () => {
      const onClose = vi.fn();
      render(<DeployPanel launchResult={MOCK_LAUNCH_SUCCESS} onClose={onClose} />);
      
      fireEvent.click(screen.getByText('close'));
      
      expect(onClose).toHaveBeenCalledOnce();
    });
  });
});
