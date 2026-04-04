/**
 * 09-memory.cy.js
 *
 * Tests the shared memory API layer — publish, query, search, context.
 * Pure HTTP — no UI interaction.
 */

describe('Memory API', () => {

  // ── GET /api/memory ───────────────────────────────────────────────────────

  describe('GET /api/memory', () => {
    it('returns 200 with entries array', () => {
      cy.request('/api/memory').then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('count').that.is.a('number');
        expect(body).to.have.property('entries').that.is.an('array');
      });
    });
  });

  // ── POST /api/memory (publish) ────────────────────────────────────────────

  describe('POST /api/memory', () => {
    it('publishes an artifact memory', () => {
      cy.request('POST', '/api/memory', {
        kind: 'artifact',
        summary: 'Created users table with id, email, password_hash columns',
        tags: ['database', 'users', 'schema'],
        room_id: 'room-test-001',
        author_role: 'engineer',
        ref: 'EPIC-001',
      }).then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('id').that.includes('mem-art');
        expect(body).to.have.property('status', 'published');
      });
    });

    it('publishes a decision memory', () => {
      cy.request('POST', '/api/memory', {
        kind: 'decision',
        summary: 'Chose JWT over sessions for stateless authentication',
        tags: ['auth', 'jwt', 'architecture'],
        room_id: 'room-test-001',
        author_role: 'engineer',
        ref: 'EPIC-001',
      }).then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body.id).to.include('mem-dec');
      });
    });

    it('publishes an interface memory with detail', () => {
      cy.request('POST', '/api/memory', {
        kind: 'interface',
        summary: 'Auth module exports verifyToken(jwt) -> {userId, role}',
        tags: ['auth', 'api', 'interface'],
        room_id: 'room-test-002',
        author_role: 'engineer',
        ref: 'EPIC-002',
        detail: 'function verifyToken(jwt: string): { userId: string, role: string }',
      }).then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body.id).to.include('mem-int');
      });
    });

    it('rejects invalid kind', () => {
      cy.request({
        method: 'POST',
        url: '/api/memory',
        body: { kind: 'invalid', summary: 'test', tags: [], room_id: 'r', author_role: 'e', ref: 'X' },
        failOnStatusCode: false,
      }).its('status').should('eq', 400);
    });
  });

  // ── GET /api/memory/query/search ──────────────────────────────────────────

  describe('GET /api/memory/query/search', () => {
    it('finds entries by text search', () => {
      cy.request('/api/memory/query/search?text=users+table').then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('results').that.is.an('array');
        expect(body.results.length).to.be.greaterThan(0);
      });
    });

    it('can exclude a room from results', () => {
      cy.request('/api/memory/query/search?text=auth&exclude_room=room-test-001').then(({ body }) => {
        body.results.forEach(entry => {
          expect(entry.room_id).to.not.eq('room-test-001');
        });
      });
    });

    it('returns empty for nonsense query', () => {
      cy.request('/api/memory/query/search?text=xyzzyplugh').then(({ body }) => {
        expect(body.results).to.have.length(0);
      });
    });
  });

  // ── GET /api/memory/context/{room_id} ─────────────────────────────────────

  describe('GET /api/memory/context/{room_id}', () => {
    it('returns context excluding own room', () => {
      cy.request('/api/memory/context/room-test-001').then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('room_id', 'room-test-001');
        expect(body).to.have.property('entries').that.is.an('array');
        // Should not contain entries from room-test-001
        body.entries.forEach(entry => {
          expect(entry.room_id).to.not.eq('room-test-001');
        });
      });
    });

    it('filters by keywords', () => {
      cy.request('/api/memory/context/room-test-003?keywords=auth,jwt').then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body.entries.length).to.be.greaterThan(0);
      });
    });
  });

  // ── GET /api/memory/stats ─────────────────────────────────────────────────

  describe('GET /api/memory/stats', () => {
    it('returns aggregate stats', () => {
      cy.request('/api/memory/stats').then(({ status, body }) => {
        expect(status).to.eq(200);
        expect(body).to.have.property('total').that.is.a('number');
        expect(body).to.have.property('by_kind').that.is.an('object');
        expect(body).to.have.property('by_room').that.is.an('object');
      });
    });
  });

  // ── GET /api/memory/{id} ──────────────────────────────────────────────────

  describe('GET /api/memory/{id}', () => {
    it('retrieves a published entry by ID', () => {
      // First publish, then fetch
      cy.request('POST', '/api/memory', {
        kind: 'convention',
        summary: 'All timestamps must be UTC ISO-8601',
        tags: ['convention', 'timestamps'],
        room_id: 'room-test-003',
        author_role: 'engineer',
        ref: 'EPIC-003',
      }).then(({ body }) => {
        cy.request(`/api/memory/${body.id}`).then(({ status, body: entry }) => {
          expect(status).to.eq(200);
          expect(entry).to.have.property('kind', 'convention');
          expect(entry).to.have.property('summary').that.includes('UTC');
        });
      });
    });

    it('returns 404 for unknown ID', () => {
      cy.request({ url: '/api/memory/mem-nonexistent', failOnStatusCode: false })
        .its('status').should('eq', 404);
    });
  });

  // ── Supersedes ────────────────────────────────────────────────────────────

  describe('Supersedes', () => {
    it('superseded entries are excluded from queries', () => {
      // Publish original
      cy.request('POST', '/api/memory', {
        kind: 'convention',
        summary: 'Use snake_case for all API fields',
        tags: ['naming', 'api'],
        room_id: 'room-test-004',
        author_role: 'engineer',
        ref: 'EPIC-004',
      }).then(({ body: original }) => {
        // Publish superseding entry
        cy.request('POST', '/api/memory', {
          kind: 'convention',
          summary: 'Use camelCase for all API fields (changed from snake_case)',
          tags: ['naming', 'api'],
          room_id: 'room-test-004',
          author_role: 'engineer',
          ref: 'EPIC-004',
          supersedes: original.id,
        }).then(() => {
          // Query should not include the original
          cy.request('/api/memory').then(({ body }) => {
            const ids = body.entries.map(e => e.id);
            expect(ids).to.not.include(original.id);
          });
        });
      });
    });
  });
});
