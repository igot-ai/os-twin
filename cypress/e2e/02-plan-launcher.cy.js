/**
 * 02-plan-launcher.cy.js
 *
 * Tests the Plan Launcher panel:
 * - textarea pre-fill
 * - quick-action template buttons
 * - LAUNCH button state while manager is running
 * - STOP button appears and kills the manager
 */

describe('Plan Launcher', () => {
  beforeEach(() => {
    cy.task('resetAgentOS');
    cy.visit('/');
  });

  // ── Textarea ─────────────────────────────────────────────────────────────

  it('textarea is pre-filled with a valid plan template', () => {
    cy.get('#plan-input')
      .should('contain.value', '# Plan:')
      .and('contain.value', '## Epic:');
  });

  it('textarea accepts typed input', () => {
    cy.get('#plan-input').clear().type('# Plan: Test', { delay: 0 });
    cy.get('#plan-input').should('have.value', '# Plan: Test');
  });

  // ── Quick Action Templates ────────────────────────────────────────────────

  it('"hello world" template fills a 1-epic hello plan', () => {
    cy.contains('button', 'hello world').click();
    cy.get('#plan-input')
      .should('contain.value', 'Hello World')
      .and('contain.value', 'EPIC-001');
  });

  it('"REST API" template fills a 2-epic API plan', () => {
    cy.contains('button', 'REST API').click();
    cy.get('#plan-input')
      .should('contain.value', 'REST API')
      .and('contain.value', 'EPIC-001')
      .and('contain.value', 'EPIC-002');
  });

  it('"full-stack app" template fills a 3-epic plan', () => {
    cy.contains('button', 'full-stack app').click();
    cy.get('#plan-input')
      .should('contain.value', 'Full-Stack')
      .and('contain.value', 'EPIC-001')
      .and('contain.value', 'EPIC-002')
      .and('contain.value', 'EPIC-003');
  });

  // ── LAUNCH Button ─────────────────────────────────────────────────────────

  it('LAUNCH button is visible and enabled by default', () => {
    cy.get('#launch-btn').should('be.visible').and('not.be.disabled');
    cy.get('#launch-text').should('contain', 'LAUNCH');
  });

  it('STOP button is hidden while no manager is running', () => {
    cy.get('#stop-btn').should('not.be.visible');
  });

  it('shows error status when plan has no tasks', () => {
    cy.get('#plan-input').clear().type('# Plan: Empty\n\n## Config\nworking_dir: .', { delay: 0 });
    cy.get('#launch-btn').click();
    cy.get('#launch-status', { timeout: 8000 }).should('contain', '✗');
  });

  it('launches successfully and shows status message', () => {
    cy.fixture('hello-plan.md').then(plan => {
      cy.get('#plan-input').clear().type(plan, { delay: 0 });
      cy.get('#launch-btn').click();
      cy.get('#launch-status', { timeout: 10000 }).should('contain', '✓ Launched');
    });
  });

  // ── STOP Button ───────────────────────────────────────────────────────────

  it('STOP button appears once a plan is launched', () => {
    cy.fixture('hello-plan.md').then(plan => {
      cy.get('#plan-input').clear().type(plan, { delay: 0 });
      cy.get('#launch-btn').click();
      // After launching, manager.pid should be created and status polled
      cy.get('#stop-btn', { timeout: 5000 }).should('be.visible');
    });
  });

  it('STOP button kills the manager and reverts button state', () => {
    cy.fixture('hello-plan.md').then(plan => {
      cy.get('#plan-input').clear().type(plan, { delay: 0 });
      cy.get('#launch-btn').click();
      cy.get('#stop-btn', { timeout: 5000 }).should('be.visible').click();
      cy.get('#launch-status', { timeout: 5000 }).should('contain', 'Stopped');
      cy.get('#stop-btn').should('not.be.visible');
      cy.get('#launch-text').should('contain', 'LAUNCH');
    });
  });
});
