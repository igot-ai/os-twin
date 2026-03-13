/// <reference types="cypress" />

describe('Global Notifications', () => {
  beforeEach(() => {
    cy.task('resetAgentOS');
    cy.visit('/');
  });

  it('renders the notification bell', () => {
    cy.get('#notification-bell').should('be.visible');
  });

  it('toggles the notification dropdown when bell is clicked', () => {
    // Should be hidden initially
    cy.get('#notification-dropdown').should('not.be.visible');

    // Click to show
    cy.get('#notification-bell').click();
    cy.get('#notification-dropdown').should('be.visible');

    // Check header
    cy.get('.notification-header').contains('Notifications');

    // Click outside to hide
    cy.get('body').click(10, 10);
    cy.get('#notification-dropdown').should('not.be.visible');
  });

  it('shows unread badge and updates it on new WebSocket event', () => {
    cy.fixture('hello-plan.md').then(plan => {
      cy.get('#plan-input').clear().type(plan, { delay: 0 });
      cy.get('#launch-btn').click();
      cy.get('#launch-status', { timeout: 10000 }).should('contain', '✓ Launched');
    });

    // After launching, the backend will process the plan and send room_created over WS
    cy.get('#notification-badge', { timeout: 15000 }).should('be.visible');

    // Clicking the bell should show the notification and clear the badge
    cy.get('#notification-bell').click();
    cy.get('#global-notification-list').contains('War-room created', { timeout: 10000 });
    
    // Stop the manager to cleanup
    cy.get('#stop-btn', { timeout: 10000 }).should('be.visible').click();
  });
});
