/**
 * 03-api.cy.js
 *
 * Tests the FastAPI backend contract directly via cy.request.
 * No UI interaction — pure HTTP.
 */

describe('API Contract', () => {
  // ── GET /api/rooms ────────────────────────────────────────────────────────

  describe('GET /api/rooms', () => {
    it('returns 200 with a rooms array', () => {
      cy.request('/api/rooms').then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('rooms').that.is.an('array');
      });
    });

    it('each room has required fields', () => {
      cy.request('/api/rooms').then(({ body }) => {
        body.rooms.forEach(room => {
          expect(room).to.have.all.keys(
            'room_id', 'status', 'task_ref', 'task_description',
            'message_count', 'retries', 'last_activity'
          );
        });
      });
    });

    it('room status is a known value', () => {
      const VALID = ['pending', 'engineering', 'qa-review', 'fixing', 'passed', 'failed-final'];
      cy.request('/api/rooms').then(({ body }) => {
        body.rooms.forEach(room => {
          expect(VALID).to.include(room.status);
        });
      });
    });
  });

  // ── GET /api/rooms/{id}/channel ───────────────────────────────────────────

  describe('GET /api/rooms/{id}/channel', () => {
    it('returns 200 with messages array for existing room', () => {
      cy.request('/api/rooms').then(({ body }) => {
        if (body.rooms.length === 0) return; // skip if no rooms
        const id = body.rooms[0].room_id;
        cy.request(`/api/rooms/${id}/channel`).then(({ status, body: ch }) => {
          expect(status).to.eq(200);
          expect(ch).to.have.property('messages').that.is.an('array');
        });
      });
    });

    it('returns 404 for a non-existent room', () => {
      cy.request({ url: '/api/rooms/room-999/channel', failOnStatusCode: false })
        .its('status').should('eq', 404);
    });

    it('each message has required fields', () => {
      cy.request('/api/rooms').then(({ body }) => {
        if (body.rooms.length === 0) return;
        const id = body.rooms[0].room_id;
        cy.request(`/api/rooms/${id}/channel`).then(({ body: ch }) => {
          ch.messages.forEach(msg => {
            expect(msg).to.have.property('id');
            expect(msg).to.have.property('type');
            expect(msg).to.have.property('ts');
          });
        });
      });
    });
  });

  // ── GET /api/status ───────────────────────────────────────────────────────

  describe('GET /api/status', () => {
    it('returns 200 with running boolean', () => {
      cy.request('/api/status').then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('running').that.is.a('boolean');
      });
    });

    it('returns pid=null when no manager is running (after reset)', () => {
      cy.task('resetAgentOS');
      cy.request('/api/status').then(({ body }) => {
        expect(body.running).to.eq(false);
        expect(body.pid).to.be.null;
      });
    });
  });

  // ── POST /api/stop ────────────────────────────────────────────────────────

  describe('POST /api/stop', () => {
    it('returns 200 when no manager running', () => {
      cy.task('resetAgentOS');
      cy.request({ method: 'POST', url: '/api/stop' }).then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body.stopped).to.eq(false);
      });
    });
  });

  // ── GET /api/release ──────────────────────────────────────────────────────

  describe('GET /api/release', () => {
    it('returns 200 with available boolean', () => {
      cy.request('/api/release').then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('available').that.is.a('boolean');
      });
    });

    it('content is a string when available', () => {
      cy.request('/api/release').then(({ body }) => {
        if (body.available) {
          expect(body.content).to.be.a('string').and.not.be.empty;
        }
      });
    });
  });

  // ── GET /api/config ───────────────────────────────────────────────────────

  describe('GET /api/config', () => {
    it('returns manager config with required fields', () => {
      cy.request('/api/config').then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('manager');
        // Use include.keys — config may have additional fields
        expect(body.manager).to.include.keys(
          'max_concurrent_rooms', 'poll_interval_seconds', 'max_engineer_retries'
        );
      });
    });

    it('max_concurrent_rooms is a positive integer', () => {
      cy.request('/api/config').then(({ body }) => {
        expect(body.manager.max_concurrent_rooms).to.be.a('number').and.be.greaterThan(0);
      });
    });
  });

  // ── POST /api/run ─────────────────────────────────────────────────────────

  describe('POST /api/run', () => {
    beforeEach(() => cy.task('resetAgentOS'));
    afterEach(() => cy.task('resetAgentOS'));

    it('rejects empty plan with 422', () => {
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: '' },
        headers: { 'Content-Type': 'application/json' },
        failOnStatusCode: false,
      }).its('status').should('eq', 422);
    });

    it('rejects a plan with no tasks', () => {
      cy.request({
        method: 'POST', url: '/api/run',
        body: { plan: '# Plan: No tasks\n\n## Config\nworking_dir: .' },
        headers: { 'Content-Type': 'application/json' },
        failOnStatusCode: false,
      }).its('status').should('be.oneOf', [400, 422, 500]);
    });

    it('accepts a valid plan and returns launched status', () => {
      cy.fixture('hello-plan.md').then(plan => {
        cy.request({
          method: 'POST', url: '/api/run',
          body: { plan },
          headers: { 'Content-Type': 'application/json' },
        }).then(({ status, body }) => {
          expect(status).to.eq(200);
          expect(body.status).to.eq('launched');
          expect(body.plan_file).to.match(/agent-os-plan-.+\.md$/);
        });
      });
    });
  });

  // ── GET /api/events (SSE) ─────────────────────────────────────────────────
  // SSE streams never terminate so cy.request() would hang.
  // Instead we verify the endpoint via cy.intercept() after page load.

  describe('GET /api/events', () => {
    // EventSource connections are not captured by cy.intercept in headless mode.
    // We verify the connection indirectly: the app sets conn-status to LIVE
    // only after the EventSource onopen fires.
    it('app SSE connection shows LIVE within 5 s of page load', () => {
      cy.visit('/');
      cy.get('#conn-status', { timeout: 5000 }).should('have.text', 'LIVE');
    });
  });
});
