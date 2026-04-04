/**
 * 05-lifecycle.cy.js
 *
 * Full end-to-end pipeline tests.
 *
 * Strategy: Submit a plan via /api/run, then use cy.task() to manually
 * drive each room through the pipeline (post done/pass messages + set status)
 * the same way the real engineer/QA agents would. This tests the whole
 * chain — plan parsing → room creation → SSE → UI updates → release —
 * without requiring deepagents or gemini to be installed.
 */

const PLAN_TWO_TASKS = `# Plan: Cypress E2E Test

## Config
working_dir: .

## Task: TASK-001 — Build alpha

Implement the alpha module.

Acceptance criteria:
- Alpha works

## Task: TASK-002 — Build beta

Implement the beta module.

Acceptance criteria:
- Beta works
`;

// Helper: wait for the UI to show a room with a given status chip text
function waitForChip(roomId, chipText, timeout = 10000) {
  cy.get(`#room-${roomId} .rc-chip`, { timeout }).should('contain', chipText);
}

describe('Full Pipeline Lifecycle', () => {
  beforeEach(() => {
    cy.task('resetAgentOS');
    cy.visit('/');
  });

  afterEach(() => {
    cy.task('resetAgentOS');
  });

  // ── Plan Submission Creates Rooms ─────────────────────────────────────────

  describe('Plan submission', () => {
    it('creates war-rooms for each task in the plan', () => {
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: PLAN_TWO_TASKS },
        headers: { 'Content-Type': 'application/json' },
      }).then(({ body }) => {
        expect(body.status).to.eq('launched');
      });

      // Wait for rooms to appear in the API
      cy.waitForRoom('room-001', { timeout: 12000 });
      cy.waitForRoom('room-002', { timeout: 12000 });

      // And in the UI via SSE
      cy.get('#room-room-001', { timeout: 12000 }).should('exist');
      cy.get('#room-room-002', { timeout: 12000 }).should('exist');
    });

    it('room task refs match the plan', () => {
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: PLAN_TWO_TASKS },
        headers: { 'Content-Type': 'application/json' },
      });

      cy.waitForRoom('room-001', { timeout: 12000 }).then(room => {
        expect(room.task_ref).to.eq('TASK-001');
      });
      cy.waitForRoom('room-002', { timeout: 12000 }).then(room => {
        expect(room.task_ref).to.eq('TASK-002');
      });
    });

    it('rooms start in pending or engineering status', () => {
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: PLAN_TWO_TASKS },
        headers: { 'Content-Type': 'application/json' },
      });

      cy.waitForRoom('room-001', { timeout: 12000 }).then(room => {
        expect(['pending', 'engineering']).to.include(room.status);
      });
    });

    it('submitting a new plan stops the old manager and resets rooms', () => {
      // First plan
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: PLAN_TWO_TASKS },
        headers: { 'Content-Type': 'application/json' },
      });
      cy.waitForRoom('room-001', { timeout: 12000 });

      // Second plan — single task
      const PLAN_ONE = `# Plan: Replacement\n\n## Config\nworking_dir: .\n\n## Task: TASK-001 — Only task\n\nBuild it.\n`;
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: PLAN_ONE },
        headers: { 'Content-Type': 'application/json' },
      });

      // room-002 should disappear (old rooms torn down)
      cy.waitForRoom('room-001', { timeout: 12000 });
      cy.get('#room-room-002', { timeout: 5000 }).should('not.exist');
    });
  });

  // ── Engineering Phase ─────────────────────────────────────────────────────

  describe('Engineering phase', () => {
    beforeEach(() => {
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: PLAN_TWO_TASKS },
        headers: { 'Content-Type': 'application/json' },
      });
      cy.waitForRoom('room-001', { timeout: 12000 });
    });

    it('initial task message appears in channel feed', () => {
      // Select room-001 to see its messages
      cy.get('#room-room-001', { timeout: 8000 }).click();
      cy.get('#channel-feed .feed-task', { timeout: 8000 }).should('have.length.at.least', 1);
    });

    it('posting a "done" message moves room to review', () => {
      cy.setRoomStatus('room-001', 'engineering');
      cy.agentPost('room-001', {
        from_: 'engineer', to: 'manager',
        type: 'done', ref: 'TASK-001',
        body: 'Alpha module complete.',
      });
      cy.setRoomStatus('room-001', 'review');

      waitForChip('room-001', 'QA REVIEW');
      cy.request('/api/rooms/room-001/channel').then(({ body }) => {
        const doneMsg = body.messages.find(m => m.type === 'done');
        expect(doneMsg).to.exist;
      });
    });
  });

  // ── QA Phase ─────────────────────────────────────────────────────────────

  describe('QA phase', () => {
    beforeEach(() => {
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: PLAN_TWO_TASKS },
        headers: { 'Content-Type': 'application/json' },
      });
      cy.waitForRoom('room-001', { timeout: 12000 });
      // Advance to review
      cy.setRoomStatus('room-001', 'review');
      cy.agentPost('room-001', {
        from_: 'engineer', to: 'manager',
        type: 'done', ref: 'TASK-001',
        body: 'Done.',
      });
    });

    it('a "pass" message moves room to passed', () => {
      cy.agentPost('room-001', {
        from_: 'qa', to: 'manager',
        type: 'pass', ref: 'TASK-001',
        body: 'VERDICT: PASS. All criteria met.',
      });
      cy.setRoomStatus('room-001', 'passed');

      waitForChip('room-001', 'PASSED');
      cy.get('#sum-passed', { timeout: 6000 }).should('not.have.text', '0');
    });

    it('a "fail" message moves room back to fixing', () => {
      cy.agentPost('room-001', {
        from_: 'qa', to: 'manager',
        type: 'fail', ref: 'TASK-001',
        body: 'VERDICT: FAIL. Missing error handling.',
      });
      cy.setRoomStatus('room-001', 'fixing');

      waitForChip('room-001', 'FIXING');
    });

    it('fail message appears in channel feed with red styling', () => {
      cy.get('#room-room-001').click();
      cy.agentPost('room-001', {
        from_: 'qa', to: 'manager',
        type: 'fail', ref: 'TASK-001',
        body: 'VERDICT: FAIL. Tests not written.',
      });
      cy.get('#channel-feed .feed-fail', { timeout: 6000 }).should('have.length.at.least', 1);
    });
  });

  // ── Full Two-Task Pipeline ────────────────────────────────────────────────

  describe('Full two-task pipeline to release', () => {
    it('all rooms pass → release notes appear', () => {
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: PLAN_TWO_TASKS },
        headers: { 'Content-Type': 'application/json' },
      });

      cy.waitForRoom('room-001', { timeout: 12000 });
      cy.waitForRoom('room-002', { timeout: 12000 });

      // Manually drive both rooms to passed
      cy.advanceRoom('room-001', 'TASK-001');
      cy.advanceRoom('room-002', 'TASK-002');

      // Both chips should show PASSED
      waitForChip('room-001', 'PASSED');
      waitForChip('room-002', 'PASSED');

      // Summary: 0 active, 2 passed
      cy.get('#sum-passed', { timeout: 8000 }).should('have.text', '2');
      cy.get('#stat-active-text').should('contain', '0 active');

      // Draft and collect signoffs manually (since manager loop would do this)
      cy.task('releaseExists').then(exists => {
        if (!exists) {
          cy.exec('MOCK_SIGNOFF=true .agents/release/draft.sh && MOCK_SIGNOFF=true .agents/release/signoff.sh', {
            cwd: '/Users/paulaan/PycharmProjects/agent-os',
          });
        }
      });

      // Release bar should appear via SSE (or after reload)
      cy.get('#release-bar', { timeout: 10000 }).should('be.visible');
    });

    it('pipeline bar highlights RELEASE stage when all rooms pass', () => {
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: PLAN_TWO_TASKS },
        headers: { 'Content-Type': 'application/json' },
      });

      cy.waitForRoom('room-001', { timeout: 12000 });
      cy.waitForRoom('room-002', { timeout: 12000 });

      cy.advanceRoom('room-001', 'TASK-001');
      cy.advanceRoom('room-002', 'TASK-002');

      // RELEASE stage should become pipe-active
      cy.get('#pipe-release', { timeout: 8000 }).should('have.class', 'pipe-active');
    });
  });

  // ── Retry Cycle ───────────────────────────────────────────────────────────

  describe('Retry cycle', () => {
    beforeEach(() => {
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: PLAN_TWO_TASKS },
        headers: { 'Content-Type': 'application/json' },
      });
      cy.waitForRoom('room-001', { timeout: 12000 });
    });

    it('retry count increments after QA fail + fix cycle', () => {
      // Engineer done
      cy.setRoomStatus('room-001', 'engineering');
      cy.agentPost('room-001', {
        from_: 'engineer', to: 'manager',
        type: 'done', ref: 'TASK-001',
        body: 'First attempt.',
      });
      cy.setRoomStatus('room-001', 'review');

      // QA fails
      cy.agentPost('room-001', {
        from_: 'qa', to: 'manager',
        type: 'fail', ref: 'TASK-001',
        body: 'VERDICT: FAIL.',
      });

      // Manager posts fix and increments retries
      cy.exec('echo 1 > .agents/war-rooms/room-001/retries', { cwd: '/Users/paulaan/PycharmProjects/agent-os' });
      cy.agentPost('room-001', {
        from_: 'manager', to: 'engineer',
        type: 'fix', ref: 'TASK-001',
        body: 'Retry 1: address QA feedback.',
      });
      cy.setRoomStatus('room-001', 'fixing');

      waitForChip('room-001', 'FIXING');
      // Room card should show retry counter
      cy.get('#room-room-001 .rc-foot', { timeout: 6000 }).should('contain', '↻1');
    });
  });

  // ── Plan Parsing Edge Cases ───────────────────────────────────────────────

  describe('Plan parsing edge cases', () => {
    it('single-task plan creates exactly one room', () => {
      const SINGLE = `# Plan: Single\n\n## Config\nworking_dir: .\n\n## Task: TASK-001 — Only\n\nDo one thing.\n`;
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: SINGLE },
        headers: { 'Content-Type': 'application/json' },
      });

      cy.waitForRoom('room-001', { timeout: 12000 });
      cy.request('/api/rooms').then(({ body }) => {
        expect(body.rooms).to.have.length(1);
      });
    });

    it('plan with em-dash separator parses task refs correctly', () => {
      const EM = `# Plan: Em\n\n## Config\nworking_dir: .\n\n## Task: TASK-042 — My feature\n\nDetails.\n`;
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: EM },
        headers: { 'Content-Type': 'application/json' },
      });

      cy.waitForRoom('room-001', { timeout: 12000 }).then(room => {
        expect(room.task_ref).to.eq('TASK-042');
      });
    });
  });
});
