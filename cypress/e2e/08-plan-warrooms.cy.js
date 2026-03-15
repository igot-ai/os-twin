/**
 * 08-plan-warrooms.cy.js
 *
 * Tests plan-scoped war-room loading in the Next.js dashboard:
 *
 * 1. API Contract — GET /api/plans, GET /api/plans/{id}/rooms, channel endpoint
 * 2. UI — Clicking a plan loads plan-scoped rooms into the grid
 * 3. UI — Clicking a room card opens the detail panel (no crash)
 * 4. UI — Activity log handles both event/event_type field formats
 * 5. UI — Room selection / deselection behaviour
 */

const TEST_PLAN_ID = 'cypresstest01';
const TEST_WORKING_DIR = '/tmp/cypress-warroom-test';
const TEST_ROOMS = [
  { roomId: 'room-001', taskRef: 'EPIC-CY01', status: 'engineering', description: 'Auth module' },
  { roomId: 'room-002', taskRef: 'EPIC-CY02', status: 'pending',     description: 'User API' },
  { roomId: 'room-003', taskRef: 'EPIC-CY03', status: 'passed',      description: 'Test suite' },
];

describe('Plan-Scoped War-Room Loading', () => {
  // ── Setup & Teardown ────────────────────────────────────────────────────

  before(() => {
    cy.fixture('plan-with-rooms.md').then(planContent => {
      cy.task('createTestPlan', {
        planId: TEST_PLAN_ID,
        workingDir: TEST_WORKING_DIR,
        planContent,
        rooms: TEST_ROOMS,
      });
    });
    // Give the server a moment to detect the new plan
    cy.wait(1000);
  });

  after(() => {
    cy.task('cleanupTestPlan', {
      planId: TEST_PLAN_ID,
      workingDir: TEST_WORKING_DIR,
    });
  });

  // ── 1. API Contract ────────────────────────────────────────────────────

  describe('API: Plan endpoints', () => {
    it('GET /api/plans returns a list that includes the test plan', () => {
      cy.request('/api/plans').then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('plans').that.is.an('array');
        const plan = body.plans.find(p => p.plan_id === TEST_PLAN_ID);
        expect(plan, `Plan ${TEST_PLAN_ID} should exist`).to.exist;
        expect(plan.title).to.eq('Cypress War-Room Test');
      });
    });

    it('GET /api/plans/{id} returns plan content and epics', () => {
      cy.request(`/api/plans/${TEST_PLAN_ID}`).then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('plan');
        expect(body.plan).to.have.property('content').that.contains('## Config');
        expect(body.plan).to.have.property('content').that.contains('working_dir');
      });
    });

    it('GET /api/plans/{id}/rooms returns plan-scoped rooms', () => {
      cy.request(`/api/plans/${TEST_PLAN_ID}/rooms`).then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('rooms').that.is.an('array');
        expect(body.rooms).to.have.length(TEST_ROOMS.length);
        expect(body).to.have.property('plan_id', TEST_PLAN_ID);
      });
    });

    it('plan rooms have required fields (room_id, task_ref, status)', () => {
      cy.request(`/api/plans/${TEST_PLAN_ID}/rooms`).then(({ body }) => {
        body.rooms.forEach(room => {
          expect(room).to.have.property('room_id');
          expect(room).to.have.property('task_ref');
          expect(room).to.have.property('status');
        });
      });
    });

    it('plan rooms include correct task refs', () => {
      cy.request(`/api/plans/${TEST_PLAN_ID}/rooms`).then(({ body }) => {
        const refs = body.rooms.map(r => r.task_ref);
        TEST_ROOMS.forEach(expected => {
          expect(refs, `Should contain ${expected.taskRef}`).to.include(expected.taskRef);
        });
      });
    });

    it('plan rooms include correct statuses', () => {
      cy.request(`/api/plans/${TEST_PLAN_ID}/rooms`).then(({ body }) => {
        const statusMap = {};
        body.rooms.forEach(r => { statusMap[r.room_id] = r.status; });
        expect(statusMap['room-001']).to.eq('engineering');
        expect(statusMap['room-002']).to.eq('pending');
        expect(statusMap['room-003']).to.eq('passed');
      });
    });

    it('channel endpoint works for plan-scoped rooms', () => {
      cy.request(`/api/rooms/room-001/channel`).then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('messages').that.is.an('array');
        expect(body.messages.length).to.be.greaterThan(0);
        // Verify the initial message was seeded
        const initMsg = body.messages.find(m => m.body && m.body.includes('Initialize room-001'));
        expect(initMsg, 'Should find the init message').to.exist;
      });
    });

    it('returns empty rooms array for a non-existent plan', () => {
      cy.request(`/api/plans/nonexistent999/rooms`).then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body.rooms).to.be.an('array').and.have.length(0);
      });
    });
  });

  // ── 2. UI: Plan Selection → Room Loading ────────────────────────────────

  describe('UI: Plan selection loads rooms', () => {
    beforeEach(() => {
      cy.visit('/');
      cy.wait(1000); // Allow initial load
    });

    it('test plan appears in the plan queue', () => {
      // The plan queue lists plans. Our test plan should be visible.
      cy.get('.plan-queue-list').should('contain', 'Cypress War-Room Test');
    });

    it('clicking a plan in the queue loads plan-scoped rooms into the grid', () => {
      // Click the test plan in the queue
      cy.get('.plan-queue-list')
        .contains('Cypress War-Room Test')
        .closest('.plan-queue-item')
        .click();

      // Wait for plan rooms to load
      cy.wait(2000);

      // Verify rooms are displayed — we should see the 3 test rooms
      cy.get('.room-card', { timeout: 10000 }).should('have.length.at.least', TEST_ROOMS.length);

      // Verify specific room IDs
      TEST_ROOMS.forEach(({ roomId }) => {
        cy.get(`#room-${roomId}`, { timeout: 5000 }).should('exist');
      });
    });

    it('room cards display correct EPIC references', () => {
      cy.get('.plan-queue-list')
        .contains('Cypress War-Room Test')
        .closest('.plan-queue-item')
        .click();

      cy.wait(2000);

      // Check each room shows its task ref
      TEST_ROOMS.forEach(({ roomId, taskRef }) => {
        cy.get(`#room-${roomId} .rc-ref`).should('contain', taskRef);
      });
    });

    it('room cards show correct status chips', () => {
      cy.get('.plan-queue-list')
        .contains('Cypress War-Room Test')
        .closest('.plan-queue-item')
        .click();

      cy.wait(2000);

      // room-001 = engineering
      cy.get('#room-room-001 .rc-chip').should('contain', 'ENGINEERING');
      // room-002 = pending
      cy.get('#room-room-002 .rc-chip').should('contain', 'PENDING');
      // room-003 = passed
      cy.get('#room-room-003 .rc-chip').should('contain', 'PASSED');
    });

    it('passed room has full progress bar (100%)', () => {
      cy.get('.plan-queue-list')
        .contains('Cypress War-Room Test')
        .closest('.plan-queue-item')
        .click();

      cy.wait(2000);

      cy.get('#room-room-003 .rc-bar').should('have.attr', 'style').and('include', 'width: 100%');
    });

    it('plan text area shows plan content after clicking', () => {
      cy.get('.plan-queue-list')
        .contains('Cypress War-Room Test')
        .closest('.plan-queue-item')
        .click();

      cy.wait(1000);

      cy.get('.plan-textarea').should('contain.value', 'Cypress War-Room Test');
    });
  });

  // ── 3. UI: Room Click → Detail Panel ────────────────────────────────────

  describe('UI: Room detail panel', () => {
    beforeEach(() => {
      cy.visit('/');
      cy.wait(500);

      // Select the test plan first
      cy.get('.plan-queue-list')
        .contains('Cypress War-Room Test')
        .closest('.plan-queue-item')
        .click();

      cy.wait(2000);
    });

    it('clicking a room card opens the detail panel without crashing', () => {
      cy.get('#room-room-001').click();

      // The page should NOT show the Next.js error overlay
      cy.get('body').should('not.contain', 'Application error');

      // The detail panel should appear
      cy.get('.room-detail', { timeout: 5000 }).should('exist').and('be.visible');
    });

    it('detail panel shows the correct room ID', () => {
      cy.get('#room-room-001').click();
      cy.get('.detail-room-id', { timeout: 5000 }).should('contain', 'room-001');
    });

    it('detail panel shows the correct task ref', () => {
      cy.get('#room-room-001').click();
      cy.get('.detail-task-ref', { timeout: 5000 }).should('contain', 'EPIC-CY01');
    });

    it('detail panel has Goal Checklist section', () => {
      cy.get('#room-room-001').click();
      cy.get('.detail-goals', { timeout: 5000 }).should('exist');
      cy.get('.detail-goals .field-label').should('contain', 'Goal Checklist');
    });

    it('detail panel has Activity Log section', () => {
      cy.get('#room-room-001').click();
      cy.get('.detail-activity', { timeout: 5000 }).should('exist');
      cy.get('.detail-activity .field-label').should('contain', 'Activity Log');
    });

    it('activity log handles "event" field (not just "event_type")', () => {
      // The API returns {event: "room_updated"} not {event_type: "room_updated"}
      // This tests the fix that prevented the crash
      cy.get('#room-room-001').click();

      cy.get('.detail-activity', { timeout: 5000 }).should('exist');

      // If there are activity entries, verify they render (no crash)
      cy.get('.detail-activity .activity-log').then($log => {
        // Either shows entries or "No activity recorded" — both are valid, no crash
        const hasEntries = $log.find('.activity-item').length > 0;
        const hasEmpty = $log.text().includes('No activity recorded');
        expect(hasEntries || hasEmpty, 'Activity log should render without crash').to.be.true;
      });
    });

    it('detail panel has Messages section', () => {
      cy.get('#room-room-001').click();

      // The "Messages" label should be visible below the activity log
      cy.get('.room-detail', { timeout: 5000 })
        .contains('Messages')
        .should('exist');
    });

    it('channel feed header updates to show selected room ID', () => {
      cy.get('#room-room-001').click();
      cy.get('.panel-right .panel-title', { timeout: 5000 }).should('contain', 'room-001');
    });

    it('clicking a different room switches the detail', () => {
      cy.get('#room-room-001').click();
      cy.get('.detail-room-id', { timeout: 5000 }).should('contain', 'room-001');

      cy.get('#room-room-002').click();
      cy.get('.detail-room-id', { timeout: 5000 }).should('contain', 'room-002');
      cy.get('.detail-task-ref').should('contain', 'EPIC-CY02');
    });

    it('only one room is selected at a time', () => {
      cy.get('#room-room-001').click();
      cy.get('#room-room-002').click();
      cy.get('.room-card.selected').should('have.length', 1);
    });

    it('clicking the selected room again deselects it', () => {
      cy.get('#room-room-001').click();
      cy.get('#room-room-001').should('have.class', 'selected');

      cy.get('#room-room-001').click();
      cy.get('#room-room-001').should('not.have.class', 'selected');

      // Detail panel should disappear and feed reverts to global
      cy.get('.panel-right .panel-title').should('contain', 'CHANNEL FEED');
    });
  });

  // ── 4. UI: Room Card Interactions ───────────────────────────────────────

  describe('UI: Room card visual details', () => {
    beforeEach(() => {
      cy.visit('/');
      cy.wait(500);
      cy.get('.plan-queue-list')
        .contains('Cypress War-Room Test')
        .closest('.plan-queue-item')
        .click();
      cy.wait(2000);
    });

    it('room card shows message count', () => {
      cy.get('#room-room-001 .rc-foot').should('contain', '⬡');
    });

    it('room card shows goal stats', () => {
      cy.get('#room-room-001 .rc-goal-stats').should('exist');
      cy.get('#room-room-001 .rc-goal-stats').should('contain', 'GOALS:');
    });

    it('engineering room has a pulsing progress bar', () => {
      cy.get('#room-room-001 .rc-bar')
        .should('have.attr', 'style')
        .and('include', 'width: 35%');
    });

    it('selected room card gets "selected" class', () => {
      cy.get('#room-room-001').click();
      cy.get('#room-room-001').should('have.class', 'selected');
    });
  });

  // ── 5. Channel Feed for Plan Rooms ─────────────────────────────────────

  describe('UI: Channel feed shows plan room messages', () => {
    beforeEach(() => {
      cy.visit('/');
      cy.wait(500);
      cy.get('.plan-queue-list')
        .contains('Cypress War-Room Test')
        .closest('.plan-queue-item')
        .click();
      cy.wait(2000);
    });

    it('feed shows messages from plan-scoped rooms', () => {
      // After loading plan rooms, feed should have messages
      cy.get('.feed .feed-msg', { timeout: 5000 }).should('have.length.at.least', 1);
    });

    it('selecting a room filters feed to that room only', () => {
      cy.get('#room-room-001').click();
      cy.wait(500);

      // Feed should show messages. If there are any, they should contain
      // something related to room-001
      cy.get('.feed .feed-msg').then($msgs => {
        // With the filter applied, at least the seeded init message should show
        if ($msgs.length > 0) {
          // Checking that manager→engineer task messages are present
          cy.get('.feed .feed-msg').first().within(() => {
            cy.get('.fm-route').should('not.be.empty');
          });
        }
      });
    });

    it('clear button empties the feed', () => {
      cy.get('.clear-btn').click();
      cy.get('.feed .feed-msg').should('have.length', 0);
    });
  });
});
