import {
  Plan,
  Epic,
  DashboardStats,
  Role,
  Skill,
  ChannelMessage,
  Lifecycle,
  Notification,
  DAG,
  Model
} from '@/types';

// ─────────────────────────────────────────────
// Dashboard Stats
// ─────────────────────────────────────────────
export const mockStats: DashboardStats = {
  total_plans: { value: 12, trend: { direction: 'up', delta: 3 } },
  active_epics: { value: 47, trend: { direction: 'up', delta: 8 } },
  completion_rate: { value: 72, trend: { direction: 'up', delta: 5 } },
  escalations: { value: 3, trend: { direction: 'down', delta: 1 } },
};

// ─────────────────────────────────────────────
// Plans
// ─────────────────────────────────────────────
export const mockPlans: Plan[] = [
  {
    plan_id: 'plan-001',
    title: 'Q3 Marketing Campaign',
    goal: 'Generate ad copy, visual assets, and social media content for the Q3 product launch campaign targeting enterprise customers.',
    status: 'active',
    domain: 'custom',
    epic_count: 6,
    active_epics: 3,
    completed_epics: 2,
    pct_complete: 65,
    critical_path: { completed: 2, total: 3 },
    escalations: 1,
    roles: [
      { name: 'Data Analyst', initials: 'DA', color: '#6366f1' },
      { name: 'Copywriter', initials: 'CW', color: '#f59e0b' },
      { name: 'Designer', initials: 'DS', color: '#ec4899' },
    ],
    created_at: '2026-03-20T08:00:00Z',
    updated_at: '2026-03-24T02:15:00Z',
  },
  {
    plan_id: 'plan-002',
    title: 'Risk Assessment Automation',
    goal: 'Automate the quarterly risk assessment pipeline with AI-driven analysis and compliance report generation.',
    status: 'active',
    domain: 'audit',
    epic_count: 8,
    active_epics: 4,
    completed_epics: 3,
    pct_complete: 82,
    critical_path: { completed: 3, total: 4 },
    escalations: 0,
    roles: [
      { name: 'Engineer', initials: 'EG', color: '#3b82f6' },
      { name: 'Auditor', initials: 'AU', color: '#8b5cf6' },
    ],
    created_at: '2026-03-15T10:00:00Z',
    updated_at: '2026-03-24T01:30:00Z',
  },
  {
    plan_id: 'plan-003',
    title: 'Data Pipeline v2.0',
    goal: 'Redesign the ETL pipeline for real-time streaming with Apache Kafka integration and Delta Lake storage.',
    status: 'active',
    domain: 'data',
    epic_count: 10,
    active_epics: 5,
    completed_epics: 4,
    pct_complete: 45,
    critical_path: { completed: 1, total: 3 },
    escalations: 2,
    roles: [
      { name: 'Engineer', initials: 'EG', color: '#3b82f6' },
      { name: 'Data Engineer', initials: 'DE', color: '#14b8a6' },
      { name: 'QA', initials: 'QA', color: '#10b981' },
    ],
    created_at: '2026-03-10T14:00:00Z',
    updated_at: '2026-03-23T22:45:00Z',
  },
  {
    plan_id: 'plan-004',
    title: 'Auth Service Rewrite',
    goal: 'Migrate authentication from monolith to microservice architecture with OAuth 2.1 and passkey support.',
    status: 'active',
    domain: 'software',
    epic_count: 5,
    active_epics: 2,
    completed_epics: 1,
    pct_complete: 28,
    critical_path: { completed: 0, total: 2 },
    escalations: 0,
    roles: [
      { name: 'Architect', initials: 'AR', color: '#8b5cf6' },
      { name: 'Engineer', initials: 'EG', color: '#3b82f6' },
    ],
    created_at: '2026-03-18T09:00:00Z',
    updated_at: '2026-03-24T03:00:00Z',
  },
  {
    plan_id: 'plan-005',
    title: 'SOC2 Compliance Audit',
    goal: 'Prepare and execute SOC2 Type II audit across all production systems with automated evidence collection.',
    status: 'active',
    domain: 'compliance',
    epic_count: 12,
    active_epics: 6,
    completed_epics: 5,
    pct_complete: 55,
    critical_path: { completed: 2, total: 5 },
    escalations: 0,
    roles: [
      { name: 'Auditor', initials: 'AU', color: '#8b5cf6' },
      { name: 'Engineer', initials: 'EG', color: '#3b82f6' },
      { name: 'Manager', initials: 'MG', color: '#64748b' },
    ],
    created_at: '2026-03-05T11:00:00Z',
    updated_at: '2026-03-23T18:30:00Z',
  },
  {
    plan_id: 'plan-006',
    title: 'Mobile App Redesign',
    goal: 'Complete UI/UX overhaul of the customer-facing mobile app with new design system and accessibility improvements.',
    status: 'draft',
    domain: 'software',
    epic_count: 7,
    active_epics: 0,
    completed_epics: 0,
    pct_complete: 0,
    critical_path: { completed: 0, total: 3 },
    escalations: 0,
    roles: [
      { name: 'Designer', initials: 'DS', color: '#ec4899' },
      { name: 'Engineer', initials: 'EG', color: '#3b82f6' },
    ],
    created_at: '2026-03-22T16:00:00Z',
    updated_at: '2026-03-22T16:00:00Z',
  },
];

// ─────────────────────────────────────────────
// Epics (for plan-001)
// ─────────────────────────────────────────────
export const mockEpics: Epic[] = [
  {
    epic_ref: 'EPIC-001',
    plan_id: 'plan-001',
    title: 'Internal Product Analysis',
    objective: 'Analyze internal product specifications and extract key value propositions for Q3 campaign.',
    status: 'passed',
    lifecycle_state: 'passed',
    role: 'Data Analyst',
    tasks: [
      { task_id: 'T-01', description: 'Analyze internal product specs', completed: true, assigned_role: 'Data Analyst', status: 'done', completed_at: '2026-03-21T10:42:00Z' },
      { task_id: 'T-02', description: 'Extract value propositions', completed: true, assigned_role: 'Data Analyst', status: 'done', completed_at: '2026-03-21T11:15:00Z' },
    ],
    depends_on: [],
    dependents: ['EPIC-002'],
    definition_of_done: [
      { id: 'dod-1', text: 'Product specs analyzed', verified: true, verified_by: 'QA', verified_at: '2026-03-21T11:30:00Z' },
      { id: 'dod-2', text: '4+ value propositions identified', verified: true, verified_by: 'QA', verified_at: '2026-03-21T11:32:00Z' },
    ],
    acceptance_criteria: [
      { id: 'ac-1', text: 'Each VP has supporting data points', status: 'pass' },
    ],
    progress: 100,
    retries: 0,
    max_retries: 3,
    timeout_seconds: 900,
    budget_tokens: { used: 45000, max: 500000 },
    room_id: 'room-001',
    created_at: '2026-03-20T08:00:00Z',
    started_at: '2026-03-21T10:00:00Z',
    last_state_change: '2026-03-21T11:30:00Z',
  },
  {
    epic_ref: 'EPIC-002',
    plan_id: 'plan-001',
    title: 'Competitor Research Phase',
    objective: 'Research competitor positioning, ad strategies, and market trends for Q3.',
    status: 'engineering',
    lifecycle_state: 'engineering',
    role: 'Data Analyst',
    tasks: [
      { task_id: 'T-01', description: 'Analyze internal product specs', completed: true, assigned_role: 'Lead Researcher', status: 'done', completed_at: '2026-03-22T10:42:00Z' },
      { task_id: 'T-02', description: 'Competitor Research Phase', completed: false, assigned_role: 'Lead Researcher', status: 'in-progress' },
      { task_id: 'T-03', description: 'Draft Ad Variants (Q3 focus)', completed: false, assigned_role: 'Copywriter', status: 'pending' },
      { task_id: 'T-04', description: 'A/B test copy performance', completed: false, assigned_role: 'Data Analyst', status: 'pending' },
      { task_id: 'T-05', description: 'Final review and handoff', completed: false, assigned_role: 'Manager', status: 'pending' },
    ],
    depends_on: ['EPIC-001'],
    dependents: ['EPIC-003'],
    definition_of_done: [
      { id: 'dod-1', text: '3 Ad variants generated', verified: true, verified_by: 'QA', verified_at: '2026-03-22T10:45:00Z' },
      { id: 'dod-2', text: 'Brand tone alignment check', verified: true, verified_by: 'QA', verified_at: '2026-03-22T10:46:00Z' },
      { id: 'dod-3', text: 'Social media sizing verified', verified: false },
      { id: 'dod-4', text: 'CTA links validated', verified: false },
    ],
    acceptance_criteria: [
      { id: 'ac-1', text: 'Must contain at least one question-based hook', status: 'pass' },
      { id: 'ac-2', text: 'CTA must lead to the Q3 landing page', status: 'not-evaluated' },
    ],
    progress: 40,
    retries: 0,
    max_retries: 3,
    timeout_seconds: 900,
    budget_tokens: { used: 125000, max: 500000 },
    room_id: 'room-002',
    created_at: '2026-03-20T08:00:00Z',
    started_at: '2026-03-22T10:00:00Z',
    last_state_change: '2026-03-22T10:42:00Z',
  },
  {
    epic_ref: 'EPIC-003',
    plan_id: 'plan-001',
    title: 'Content Generation',
    objective: 'Generate final ad copy variants, visual asset descriptions, and social media posts.',
    status: 'pending',
    lifecycle_state: 'pending',
    role: 'Copywriter',
    tasks: [
      { task_id: 'T-01', description: 'Generate headline variants', completed: false, assigned_role: 'Copywriter', status: 'pending' },
      { task_id: 'T-02', description: 'Write body copy', completed: false, assigned_role: 'Copywriter', status: 'pending' },
      { task_id: 'T-03', description: 'Create CTA variants', completed: false, assigned_role: 'Copywriter', status: 'pending' },
    ],
    depends_on: ['EPIC-002'],
    dependents: ['EPIC-004'],
    definition_of_done: [
      { id: 'dod-1', text: 'All copy variants proofread', verified: false },
      { id: 'dod-2', text: 'Brand guidelines met', verified: false },
    ],
    acceptance_criteria: [
      { id: 'ac-1', text: 'At least 5 headline variants', status: 'not-evaluated' },
    ],
    progress: 0,
    retries: 0,
    max_retries: 3,
    timeout_seconds: 900,
    budget_tokens: { used: 0, max: 500000 },
    room_id: 'room-003',
    created_at: '2026-03-20T08:00:00Z',
  },
  {
    epic_ref: 'EPIC-004',
    plan_id: 'plan-001',
    title: 'Visual Asset Design',
    objective: 'Create visual assets for social media, display ads, and email campaigns.',
    status: 'pending',
    lifecycle_state: 'pending',
    role: 'Designer',
    tasks: [
      { task_id: 'T-01', description: 'Design social media templates', completed: false, assigned_role: 'Designer', status: 'pending' },
      { task_id: 'T-02', description: 'Create display ad variants', completed: false, assigned_role: 'Designer', status: 'pending' },
    ],
    depends_on: ['EPIC-003'],
    dependents: [],
    definition_of_done: [
      { id: 'dod-1', text: 'All assets exported in required formats', verified: false },
    ],
    acceptance_criteria: [
      { id: 'ac-1', text: 'Assets match brand guidelines', status: 'not-evaluated' },
    ],
    progress: 0,
    retries: 0,
    max_retries: 3,
    timeout_seconds: 1200,
    budget_tokens: { used: 0, max: 300000 },
    room_id: 'room-004',
    created_at: '2026-03-20T08:00:00Z',
  },
  {
    epic_ref: 'EPIC-005',
    plan_id: 'plan-001',
    title: 'QA Review & Approval',
    objective: 'Review all generated content for quality, brand compliance, and campaign readiness.',
    status: 'passed',
    lifecycle_state: 'passed',
    role: 'QA',
    tasks: [
      { task_id: 'T-01', description: 'Review copy quality', completed: true, assigned_role: 'QA', status: 'done', completed_at: '2026-03-22T14:00:00Z' },
      { task_id: 'T-02', description: 'Verify brand tone', completed: true, assigned_role: 'QA', status: 'done', completed_at: '2026-03-22T14:30:00Z' },
    ],
    depends_on: [],
    dependents: ['EPIC-002'],
    definition_of_done: [
      { id: 'dod-1', text: 'All items reviewed', verified: true, verified_by: 'QA', verified_at: '2026-03-22T15:00:00Z' },
    ],
    acceptance_criteria: [
      { id: 'ac-1', text: 'No critical issues found', status: 'pass' },
    ],
    progress: 100,
    retries: 0,
    max_retries: 3,
    timeout_seconds: 600,
    budget_tokens: { used: 35000, max: 300000 },
    room_id: 'room-005',
    created_at: '2026-03-20T08:00:00Z',
    started_at: '2026-03-22T13:00:00Z',
    last_state_change: '2026-03-22T15:00:00Z',
  },
  {
    epic_ref: 'EPIC-006',
    plan_id: 'plan-001',
    title: 'Campaign Launch Prep',
    objective: 'Final preparation and scheduling for the Q3 campaign launch across all channels.',
    status: 'fixing',
    lifecycle_state: 'fixing',
    role: 'Engineer',
    tasks: [
      { task_id: 'T-01', description: 'Set up ad platform campaigns', completed: true, assigned_role: 'Engineer', status: 'done', completed_at: '2026-03-23T09:00:00Z' },
      { task_id: 'T-02', description: 'Configure tracking pixels', completed: false, assigned_role: 'Engineer', status: 'in-progress' },
      { task_id: 'T-03', description: 'Schedule social media posts', completed: false, assigned_role: 'Engineer', status: 'pending' },
    ],
    depends_on: ['EPIC-003'],
    dependents: [],
    definition_of_done: [
      { id: 'dod-1', text: 'All campaigns configured', verified: false },
      { id: 'dod-2', text: 'Tracking verified', verified: false },
    ],
    acceptance_criteria: [
      { id: 'ac-1', text: 'All channels have scheduled content', status: 'not-evaluated' },
    ],
    progress: 33,
    retries: 1,
    max_retries: 3,
    timeout_seconds: 900,
    budget_tokens: { used: 210000, max: 500000 },
    room_id: 'room-006',
    created_at: '2026-03-20T08:00:00Z',
    started_at: '2026-03-23T08:00:00Z',
    last_state_change: '2026-03-23T12:00:00Z',
  },
  {
    epic_ref: 'EPIC-007',
    plan_id: 'plan-002',
    title: 'Risk Engine Scoping',
    objective: 'Define the scope and data sources for the risk assessment engine.',
    status: 'passed',
    lifecycle_state: 'passed',
    role: 'Auditor',
    tasks: [
      { task_id: 'T-01', description: 'Identify data sources', completed: true, assigned_role: 'Auditor', status: 'done' },
      { task_id: 'T-02', description: 'Define risk metrics', completed: true, assigned_role: 'Auditor', status: 'done' },
    ],
    depends_on: [],
    dependents: [],
    definition_of_done: [
      { id: 'dod-1', text: 'Data sources identified', verified: true },
    ],
    acceptance_criteria: [
      { id: 'ac-1', text: 'At least 3 sources identified', status: 'pass' },
    ],
    progress: 100,
    retries: 0,
    max_retries: 3,
    timeout_seconds: 600,
    budget_tokens: { used: 12000, max: 200000 },
    room_id: 'room-007',
    created_at: '2026-03-15T10:00:00Z',
    started_at: '2026-03-16T09:00:00Z',
  },
];

// ─────────────────────────────────────────────
// Channel Messages (for EPIC-002)
// ─────────────────────────────────────────────
export const mockMessages: ChannelMessage[] = [
  {
    id: 'msg-001',
    ts: '2026-03-22T10:42:01.012Z',
    from: 'System',
    to: 'Data Analyst',
    type: 'task',
    ref: 'EPIC-002',
    body: 'Epic EPC-8924-MKQ3 initialized. Delegating Task 1 to Data Analyst (Agent ID: DA-992).',
    lifecycle_state: 'engineering',
  },
  {
    id: 'msg-002',
    ts: '2026-03-22T10:42:03.110Z',
    from: 'Data Analyst',
    to: 'System',
    type: 'design-guidance',
    ref: 'EPIC-002',
    body: 'Analyzing internal product specs for Q3 feature release... Internal analysis complete. 4 key value propositions identified.',
    lifecycle_state: 'engineering',
  },
  {
    id: 'msg-003',
    ts: '2026-03-22T10:42:10.840Z',
    from: 'Security',
    to: 'System',
    type: 'escalate',
    ref: 'EPIC-002',
    body: "Policy requires human approval for external requests in this workspace. Attempted tool: `'WebBrowsing'`.",
    lifecycle_state: 'engineering',
  },
  {
    id: 'msg-004',
    ts: '2026-03-22T10:45:00.000Z',
    from: 'QA',
    to: 'Data Analyst',
    type: 'qa-result',
    ref: 'EPIC-002',
    body: '**QA Review Complete**\n\n✅ Ad variants meet minimum quantity (3/3)\n✅ Brand tone alignment verified\n⏳ Social media sizing — pending verification\n\nOverall: Partial pass. One remaining item.',
    lifecycle_state: 'review',
  },
  {
    id: 'msg-005',
    ts: '2026-03-22T10:48:00.000Z',
    from: 'Engineer',
    to: 'QA',
    type: 'done',
    ref: 'EPIC-002',
    body: '🔧 Calling tool: `resize_images`\n\nAll social media sizing updated to spec:\n- Instagram: 1080×1080\n- Twitter: 1200×675\n- LinkedIn: 1200×627',
    lifecycle_state: 'fixing',
  },
  {
    id: 'msg-006',
    ts: '2026-03-22T10:50:00.000Z',
    from: 'System',
    to: 'Manager',
    type: 'escalate',
    ref: 'EPIC-002',
    body: 'Escalation triggered: EPIC-002 failed QA review 3 times. Manual intervention required.',
    lifecycle_state: 'manager-triage',
  },
  {
    id: 'msg-007',
    ts: '2026-03-22T11:00:00.000Z',
    from: 'Manager',
    to: 'System',
    type: 'plan-approve',
    ref: 'EPIC-002',
    body: 'Retrying EPIC-002 with Claude Opus. Increased budget to 1M tokens.',
    lifecycle_state: 'manager-triage',
  },
  {
    id: 'msg-008',
    ts: '2026-03-22T11:05:00.000Z',
    from: 'System',
    to: 'Engineer',
    type: 'task',
    ref: 'EPIC-002',
    body: 'Retrying task: Generate Ad Variants. Role: Lead Engineer (Agent ID: EG-001).',
    lifecycle_state: 'engineering',
  },
  {
    id: 'msg-009',
    ts: '2026-03-22T11:15:00.000Z',
    from: 'Engineer',
    to: 'System',
    type: 'fix',
    ref: 'EPIC-002',
    body: 'Applied fixes to content generation logic to handle brand tone constraints better.',
    lifecycle_state: 'fixing',
  },
  {
    id: 'msg-010',
    ts: '2026-03-22T11:30:00.000Z',
    from: 'QA',
    to: 'System',
    type: 'qa-result',
    ref: 'EPIC-002',
    body: 'Final QA Review: All items passed. Recommending for signoff.',
    lifecycle_state: 'review',
  },
  {
    id: 'msg-011',
    ts: '2026-03-22T11:45:00.000Z',
    from: 'System',
    to: 'Plan Owner',
    type: 'done',
    ref: 'EPIC-002',
    body: 'EPIC-002 successfully completed and passed QA.',
    lifecycle_state: 'passed',
  },
];

// ─────────────────────────────────────────────
// Lifecycle (for plan-001 EPICs)
// ─────────────────────────────────────────────
export const mockLifecycle: Lifecycle = {
  initial_state: 'pending',
  states: {
    pending: {
      name: 'Pending',
      type: 'builtin',
      role: 'system',
      transitions: { start: 'engineering' },
    },
    engineering: {
      name: 'Engineering',
      type: 'agent',
      role: 'engineer',
      transitions: { done: 'review', fail: 'fixing' },
    },
    'review': {
      name: 'QA Review',
      type: 'agent',
      role: 'qa',
      transitions: { pass: 'passed', fail: 'fixing', escalate: 'manager-triage' },
    },
    fixing: {
      name: 'Fixing',
      type: 'agent',
      role: 'engineer',
      transitions: { done: 'review', fail: 'manager-triage' },
    },
    'manager-triage': {
      name: 'Manager Triage',
      type: 'builtin',
      role: 'manager',
      transitions: { retry: 'engineering', escalate: 'failed-final' },
    },
    passed: {
      name: 'Passed',
      type: 'builtin',
      role: 'system',
      transitions: { signoff: 'signoff' },
    },
    signoff: {
      name: 'Signoff',
      type: 'builtin',
      role: 'system',
      transitions: {},
    },
  },
};

// ─────────────────────────────────────────────
// Roles
// ─────────────────────────────────────────────
export const mockRoles: Role[] = [
  {
    id: 'role-001',
    name: 'engineer',
    provider: 'claude',
    version: 'claude-sonnet-4-6',
    temperature: 0.3,
    budget_tokens_max: 500000,
    max_retries: 3,
    timeout_seconds: 900,
    skill_refs: ['implement-epic', 'fix-from-qa'],
  },
  {
    id: 'role-002',
    name: 'qa',
    provider: 'claude',
    version: 'claude-sonnet-4-6',
    temperature: 0.2,
    budget_tokens_max: 300000,
    max_retries: 3,
    timeout_seconds: 600,
    skill_refs: ['review-epic'],
  },
  {
    id: 'role-003',
    name: 'architect',
    provider: 'gpt',
    version: 'gpt-4o',
    temperature: 0.4,
    budget_tokens_max: 600000,
    max_retries: 2,
    timeout_seconds: 1200,
    skill_refs: ['review-epic', 'triage-escalation'],
  },
  {
    id: 'role-004',
    name: 'auditor',
    provider: 'gemini',
    version: 'google-vertex/gemini-2.5-pro',
    temperature: 0.1,
    budget_tokens_max: 600000,
    max_retries: 2,
    timeout_seconds: 1200,
    skill_refs: ['compliance-check'],
  },
];

// ─────────────────────────────────────────────
// Skills
// ─────────────────────────────────────────────
export const mockSkills: Skill[] = [
  {
    id: 'skill-001', name: 'implement-epic', version: '2.1',
    description: 'Core implementation skill — reads the EPIC config, executes tasks sequentially, writes code, and produces artifacts.',
    category: 'implementation', applicable_roles: ['engineer'], usage_count: 24,
  },
  {
    id: 'skill-002', name: 'review-epic', version: '1.4',
    description: 'Reviews EPIC output against Definition of Done and Acceptance Criteria, produces a QA report.',
    category: 'review', applicable_roles: ['qa', 'architect'], usage_count: 18,
  },
  {
    id: 'skill-003', name: 'fix-from-qa', version: '1.2',
    description: 'Reads QA feedback, identifies failing items, and applies targeted fixes to the codebase.',
    category: 'implementation', applicable_roles: ['engineer'], usage_count: 15,
  },
  {
    id: 'skill-004', name: 'triage-escalation', version: '1.0',
    description: 'Analyzes escalated issues, determines root cause, and recommends resolution path.',
    category: 'triage', applicable_roles: ['architect', 'manager'], usage_count: 6,
  },
  {
    id: 'skill-005', name: 'compliance-check', version: '1.1',
    description: 'Runs compliance checks against SOC2, GDPR, and HIPAA frameworks.',
    category: 'compliance', applicable_roles: ['auditor'], usage_count: 8,
  },
  {
    id: 'skill-006', name: 'write-documentation', version: '1.3',
    description: 'Generates technical documentation, API references, and user guides from codebase.',
    category: 'writing', applicable_roles: ['engineer', 'technical-writer'], usage_count: 12,
  },
  {
    id: 'skill-007', name: 'test-generation', version: '1.0',
    description: 'Generates unit tests, integration tests, and E2E test suites for given code modules.',
    category: 'testing', applicable_roles: ['qa', 'engineer'], usage_count: 9,
  },
];

// ──────────────────────────────────────────────────
// DAG
// ──────────────────────────────────────────────────
export const mockDAG: Record<string, DAG> = {
  'plan-001': {
    generated_at: '2026-03-24T03:00:00Z',
    total_nodes: 6,
    max_depth: 3,
    nodes: {
      'EPIC-001': {
        room_id: 'room-001', role: 'analyst', candidate_roles: ['analyst'],
        depends_on: null, dependents: ['EPIC-002'], depth: 0, on_critical_path: true,
      },
      'EPIC-005': {
        room_id: 'room-005', role: 'qa', candidate_roles: ['qa'],
        depends_on: null, dependents: ['EPIC-002'], depth: 0, on_critical_path: false,
      },
      'EPIC-002': {
        room_id: 'room-002', role: 'analyst', candidate_roles: ['analyst'],
        depends_on: ['EPIC-001', 'EPIC-005'], dependents: ['EPIC-003'], depth: 1, on_critical_path: true,
      },
      'EPIC-003': {
        room_id: 'room-003', role: 'engineer', candidate_roles: ['engineer'],
        depends_on: 'EPIC-002', dependents: ['EPIC-004', 'EPIC-006'], depth: 2, on_critical_path: true,
      },
      'EPIC-004': {
        room_id: 'room-004', role: 'engineer', candidate_roles: ['engineer'],
        depends_on: 'EPIC-003', dependents: [], depth: 3, on_critical_path: false,
      },
      'EPIC-006': {
        room_id: 'room-006', role: 'engineer', candidate_roles: ['engineer'],
        depends_on: 'EPIC-003', dependents: [], depth: 3, on_critical_path: true,
      },
    },
    topological_order: ['EPIC-001', 'EPIC-005', 'EPIC-002', 'EPIC-003', 'EPIC-004', 'EPIC-006'],
    critical_path: ['EPIC-001', 'EPIC-002', 'EPIC-003', 'EPIC-006'],
    critical_path_length: 4,
    waves: {
      '0': ['EPIC-001', 'EPIC-005'],
      '1': ['EPIC-002'],
      '2': ['EPIC-003'],
      '3': ['EPIC-004', 'EPIC-006'],
    },
  },
};

// ─────────────────────────────────────────────
// Notifications
// ─────────────────────────────────────────────
export const mockNotifications: Notification[] = [
  {
    id: 'notif-001',
    ts: '2026-03-24T02:00:00Z',
    type: 'escalation',
    title: 'New Escalation',
    body: 'EPIC-002 requires manual approval for web browsing.',
    plan_name: 'Q3 Marketing Campaign',
    epic_ref: 'EPIC-002',
    read: false,
  },
  {
    id: 'notif-002',
    ts: '2026-03-23T18:00:00Z',
    type: 'completion',
    title: 'Epic Completed',
    body: 'EPIC-001 passed all QA checks.',
    plan_name: 'Q3 Marketing Campaign',
    epic_ref: 'EPIC-001',
    read: true,
  },
  {
    id: 'notif-003',
    ts: '2026-03-24T01:30:00Z',
    type: 'info',
    title: 'Plan Updated',
    body: 'Data Pipeline v2.0 was updated by system.',
    plan_name: 'Data Pipeline v2.0',
    read: false,
  },
];

// ─────────────────────────────────────────────
// Model Registry
// ─────────────────────────────────────────────
export const mockModels: Model[] = [
  {
    id: 'claude-sonnet-4-6',
    name: 'Claude 3.5 Sonnet',
    provider: 'claude',
    context_window: 200000,
    cost_per_1m_tokens: 3,
  },
  {
    id: 'claude-opus-3-5',
    name: 'Claude 3.5 Opus',
    provider: 'claude',
    context_window: 200000,
    cost_per_1m_tokens: 15,
  },
  {
    id: 'gpt-4o',
    name: 'GPT-4o',
    provider: 'gpt',
    context_window: 128000,
    cost_per_1m_tokens: 5,
  },
  {
    id: 'google-vertex/gemini-2.5-pro',
    name: 'Gemini 2.5 Pro',
    provider: 'gemini',
    context_window: 1000000,
    cost_per_1m_tokens: 1.25,
  },
];
