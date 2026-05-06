import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { StructuredPlanView } from '../components/plan/StructuredPlanView';
import { parseEpicMarkdown, EpicDocument } from '../lib/epic-parser';

vi.mock('../components/plan/PlanWorkspace', () => ({
  usePlanContext: () => ({
    parsedPlan: mockParsedPlan,
    updateParsedPlan: mockUpdateParsedPlan,
    setActiveTab: vi.fn(),
  }),
}));

vi.mock('../hooks/use-roles', () => ({
  useRoles: () => ({
    roles: [
      { name: 'engineer', description: 'Software engineer' },
      { name: 'qa', description: 'Quality assurance' },
    ],
  }),
}));

let mockParsedPlan: EpicDocument | null = null;
const mockUpdateParsedPlan = vi.fn();

const SAMPLE_PLAN = `# Plan: Test Plan

## Config
working_dir: /tmp/test

## High-Level Goal

Build a test system.

## EPIC-001 — First Feature

**Roles**: @engineer

### Description

This is the first feature.

### Definition of Done

- [ ] Task 1
- [x] Task 2

### Tasks

- [ ] **T-001.1** — First task
`;

describe('StructuredPlanView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockParsedPlan = parseEpicMarkdown(SAMPLE_PLAN);
  });

  it('renders plan title', () => {
    render(<StructuredPlanView />);
    expect(screen.getByText(/Test Plan/)).toBeInTheDocument();
  });

  it('renders EPIC cards', () => {
    render(<StructuredPlanView />);
    expect(screen.getByText('EPIC-001')).toBeInTheDocument();
    expect(screen.getByText('First Feature')).toBeInTheDocument();
  });

  it('shows add new EPIC button', () => {
    render(<StructuredPlanView />);
    expect(screen.getByRole('button', { name: /add new epic/i })).toBeInTheDocument();
  });

  it('shows PLAN badge', () => {
    render(<StructuredPlanView />);
    expect(screen.getByText('PLAN')).toBeInTheDocument();
  });

  it('shows EPIC count badge', () => {
    render(<StructuredPlanView />);
    expect(screen.getByText('1 EPICS')).toBeInTheDocument();
  });

  it('shows high-level goal section', () => {
    render(<StructuredPlanView />);
    expect(screen.getByText(/High-Level Goal & Configuration/i)).toBeInTheDocument();
  });

  describe('when parsedPlan is null', () => {
    beforeEach(() => {
      mockParsedPlan = null;
    });

    it('shows error state with switch to edit mode button', () => {
      render(<StructuredPlanView />);
      expect(screen.getByText(/parse error or empty plan/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /switch to edit mode/i })).toBeInTheDocument();
    });
  });

  describe('EPIC card rendering', () => {
    it('shows EPIC reference badge', () => {
      render(<StructuredPlanView />);
      const badges = screen.getAllByText('EPIC-001');
      expect(badges.length).toBeGreaterThan(0);
    });

    it('shows EPIC title', () => {
      render(<StructuredPlanView />);
      expect(screen.getByText('First Feature')).toBeInTheDocument();
    });

    it('shows Definition of Done section', () => {
      render(<StructuredPlanView />);
      expect(screen.getByText(/Definition of Done/i)).toBeInTheDocument();
    });

    it('shows Tasks section', () => {
      render(<StructuredPlanView />);
      expect(screen.getByText(/Tasks/i)).toBeInTheDocument();
    });
  });

  describe('plan title editing', () => {
    it('enters edit mode on double-click', async () => {
      render(<StructuredPlanView />);
      const title = screen.getByRole('heading', { level: 1 });
      fireEvent.dblClick(title);
      await waitFor(() => {
        const input = screen.getByDisplayValue(/Test Plan/);
        expect(input).toBeInTheDocument();
      });
    });
  });

  describe('goal editing', () => {
    it('enters edit mode on double-click', async () => {
      render(<StructuredPlanView />);
      const goalContainer = screen.getByText(/Build a test system/i).closest('div');
      if (goalContainer) {
        fireEvent.dblClick(goalContainer);
      }
      await waitFor(() => {
        const textarea = screen.getByRole('textbox');
        expect(textarea).toBeInTheDocument();
      });
    });
  });

  describe('adding new EPIC', () => {
    it('calls updateParsedPlan when add EPIC button is clicked', () => {
      render(<StructuredPlanView />);
      const addButton = screen.getByRole('button', { name: /add new epic/i });
      fireEvent.click(addButton);
      expect(mockUpdateParsedPlan).toHaveBeenCalled();
    });
  });
});
