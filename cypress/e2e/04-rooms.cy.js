/**
 * 04-rooms.cy.js
 *
 * Tests the war-room grid and channel feed UI:
 * - Room cards render with correct status / chip / progress bar
 * - Clicking a room filters the channel feed
 * - Summary chips update counts
 * - Status transitions update the card live via SSE
 */

describe('War-Room Grid & Channel Feed', () => {
  // Use the rooms already present from the web-demo pipeline run
  // (room-001..004 in "passed" state)
  before(() => {
    cy.visit('/');
  });

  // ── Room Cards ────────────────────────────────────────────────────────────

  describe('Room cards', () => {
    it('renders a card for each room returned by /api/rooms', () => {
      cy.request('/api/rooms').then(({ body }) => {
        body.rooms.forEach(({ room_id }) => {
          cy.get(`#room-${room_id}`).should('exist');
        });
      });
    });

    it('room card shows room ID and task ref', () => {
      cy.get('.room-card').first().within(() => {
        cy.get('.rc-id').should('not.be.empty');
        cy.get('.rc-ref').should('not.be.empty');
      });
    });

    it('passed rooms show PASSED chip', () => {
      cy.get('[data-status="passed"]').should('have.length.at.least', 1).each($card => {
        cy.wrap($card).find('.rc-chip').should('contain', 'PASSED');
      });
    });

    it('passed room cards have full progress bar (width 100%)', () => {
      cy.get('[data-status="passed"]').first().within(() => {
        cy.get('.rc-bar').should('have.attr', 'style').and('include', 'width: 100%');
      });
    });

    it('shows message count on each card', () => {
      cy.get('.room-card').first().within(() => {
        cy.get('.rc-foot').should('contain', '⬡');
      });
    });
  });

  // ── Summary Chips ─────────────────────────────────────────────────────────

  describe('Summary chips', () => {
    it('passed count matches number of passed room cards', () => {
      cy.get('[data-status="passed"]').then($cards => {
        const count = $cards.length;
        cy.get('#sum-passed').should('have.text', String(count));
      });
    });

    it('topbar shows correct total rooms count', () => {
      cy.request('/api/rooms').then(({ body }) => {
        cy.get('#stat-rooms-text').should('contain', String(body.rooms.length));
      });
    });
  });

  // ── Channel Feed ──────────────────────────────────────────────────────────

  describe('Channel Feed', () => {
    it('renders feed messages on load', () => {
      cy.get('#channel-feed .feed-msg').should('have.length.at.least', 1);
    });

    it('feed messages have route and type spans', () => {
      cy.get('#channel-feed .feed-msg').first().within(() => {
        cy.get('.fm-route').should('not.be.empty');
        cy.get('.fm-type').should('not.be.empty');
      });
    });

    it('"task" messages have cyan type styling', () => {
      cy.get('.feed-task .fm-type').first()
        .should('have.css', 'color', 'rgb(0, 212, 255)');
    });

    it('"pass" messages have green type styling', () => {
      cy.get('.feed-pass .fm-type').first()
        .should('have.css', 'color', 'rgb(0, 255, 136)');
    });

    it('"clear" button empties the feed', () => {
      cy.contains('button', 'clear').click();
      cy.get('#channel-feed .feed-msg').should('have.length', 0);
    });
  });

  // ── Room Selection → Feed Filter ──────────────────────────────────────────

  describe('Room selection filters the feed', () => {
    beforeEach(() => cy.visit('/'));

    it('clicking a room card adds "selected" class', () => {
      cy.get('.room-card').first().click()
        .should('have.class', 'selected');
    });

    it('feed header updates to show the selected room ID', () => {
      cy.get('.room-card').first().then($card => {
        const roomId = $card.attr('id').replace('room-', '');
        $card.trigger('click');
        cy.get('.panel-right .panel-title').should('contain', roomId);
      });
    });

    it('clicking the selected room again deselects it and restores global feed', () => {
      cy.get('.room-card').first().click().click()
        .should('not.have.class', 'selected');
      cy.get('.panel-right .panel-title').should('contain', 'CHANNEL FEED');
    });

    it('only one room can be selected at a time', () => {
      cy.get('.room-card').eq(0).click();
      cy.get('.room-card').eq(1).click();
      cy.get('.room-card.selected').should('have.length', 1);
    });
  });

  // ── SSE-Driven Status Update ──────────────────────────────────────────────

  describe('Live SSE status update', () => {
    before(() => cy.visit('/'));

    it('card status chip updates when status file changes', () => {
      // Requires at least one existing room
      cy.request('/api/rooms').then(({ body }) => {
        if (body.rooms.length === 0) return;
        const room = body.rooms[0];

        // Flip it to engineering then back to passed
        cy.task('setRoomStatus', { room: room.room_id, status: 'engineering' });

        cy.get(`#room-${room.room_id} .rc-chip`, { timeout: 6000 })
          .should('contain', 'ENGINEERING');

        cy.task('setRoomStatus', { room: room.room_id, status: 'passed' });

        cy.get(`#room-${room.room_id} .rc-chip`, { timeout: 6000 })
          .should('contain', 'PASSED');
      });
    });

    it('a new message posted via bash appears in the feed', () => {
      cy.request('/api/rooms').then(({ body }) => {
        if (body.rooms.length === 0) return;
        const room = body.rooms[0];
        const uniqueBody = `cypress-test-msg-${Date.now()}`;

        // Select that room's feed
        cy.get(`#room-${room.room_id}`).click();

        cy.agentPost(room.room_id, {
          from_: 'engineer', to: 'manager',
          type: 'done', ref: room.task_ref,
          body: uniqueBody,
        });

        cy.get('#channel-feed', { timeout: 6000 })
          .should('contain', uniqueBody.slice(0, 30));
      });
    });
  });
});
