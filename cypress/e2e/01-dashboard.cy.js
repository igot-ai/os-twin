/**
 * 01-dashboard.cy.js
 *
 * Verifies the static layout of the Agent OS Command Center:
 * topbar, pipeline bar, three panels, and SSE connection indicator.
 */

describe('Dashboard Layout', () => {
  beforeEach(() => {
    cy.visit('/');
  });

  it('has the correct page title', () => {
    cy.title().should('eq', '⬡ Agent OS — Command Center');
  });

  // ── Topbar ──────────────────────────────────────────────────────────────

  describe('Topbar', () => {
    it('shows the AgentOS logo and version', () => {
      cy.get('.topbar-logo').should('contain', 'AGENT').and('contain', 'OS');
      cy.get('.logo-version').should('contain', 'v0.1.0');
    });

    it('shows stat pills for active / passed / rooms', () => {
      cy.get('#stat-active-text').should('exist');
      cy.get('#stat-passed-text').should('exist');
      cy.get('#stat-rooms-text').should('exist');
    });

    it('shows LIVE connection status within 5 s', () => {
      cy.get('#conn-status', { timeout: 5000 }).should('contain', 'LIVE');
    });

    it('connection dot turns green when live', () => {
      cy.get('#conn-dot', { timeout: 5000 }).should(($el) => {
        const bg = $el.css('background-color');
        // rgb of #00ff88
        expect(bg).to.match(/rgb\(0,\s*255,\s*136\)/);
      });
    });
  });

  // ── Pipeline Bar ─────────────────────────────────────────────────────────

  describe('Pipeline Bar', () => {
    it('shows all four pipeline stages', () => {
      cy.get('#pipe-manager').should('contain', 'MANAGER');
      cy.get('#pipe-engineer').should('contain', 'ENGINEER');
      cy.get('#pipe-qa').should('contain', 'QA');
      cy.get('#pipe-release').should('contain', 'RELEASE');
    });

    it('has animated arrows between stages', () => {
      cy.get('.pipeline-arrow').should('have.length', 3);
    });
  });

  // ── Three-Panel Layout ───────────────────────────────────────────────────

  describe('Three-panel layout', () => {
    it('renders the Plan Launcher panel', () => {
      cy.get('.panel-left').should('exist');
      cy.contains('.panel-title', 'PLAN LAUNCHER').should('exist');
    });

    it('renders the War-Rooms panel', () => {
      cy.get('.panel-center').should('exist');
      cy.contains('.panel-title', 'WAR-ROOMS').should('exist');
    });

    it('renders the Channel Feed panel', () => {
      cy.get('.panel-right').should('exist');
      cy.contains('CHANNEL FEED').should('exist');
    });
  });

  // ── System Config ────────────────────────────────────────────────────────

  describe('System Config section', () => {
    it('displays loaded config values', () => {
      cy.get('#cfg-concurrent').should('not.contain', '—');
      cy.get('#cfg-poll').should('not.contain', '—');
      cy.get('#cfg-retries').should('not.contain', '—');
    });
  });
});
