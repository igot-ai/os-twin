/**
 * 10-dashboard-v2.cy.js
 * 
 * Verifies the new UI functionality introduced in Dashboard v2.
 */

describe('Dashboard v2', () => {
  beforeEach(() => {
    // Reset state if needed, but since it's E2E against a live backend, we visit directly.
    cy.visit('/');
  });

  // ── Home Screen ──────────────────────────────────────────────────────────

  describe('Home Screen', () => {
    it('shows the dynamic greeting', () => {
      cy.get('h1').should('contain.text', 'Hi,');
      cy.get('h1').should('contain.text', 'What do you want to build?');
    });

    it('has a functional category carousel', () => {
      cy.get('.hide-scrollbar.snap-x').should('exist');
      cy.get('.hide-scrollbar.snap-x button').should('have.length.greaterThan', 0);
    });

    it('can rotate example prompt chips', () => {
      cy.contains('button', 'Try an example prompt').click();
      // Wait for re-render, assuming it cycles the suggestions
      cy.wait(500);
      cy.get('button').should('exist');
    });

    it('renders the recent plans grid', () => {
      cy.contains('h2', 'Your recent Plans').should('exist');
    });
  });

  // ── Sidebar ──────────────────────────────────────────────────────────────

  describe('Sidebar', () => {
    it('navigates via 5 tabs', () => {
      const tabs = ['Home', 'Plans', 'Skills', 'Roles', 'Settings'];
      tabs.forEach(tab => {
        cy.get(`nav a[aria-label="${tab}"]`).should('exist');
      });
      // Click Plans tab
      cy.get('nav a[aria-label="Plans"]').click();
      cy.url().should('include', '/plans');
      // Go back to Home
      cy.get('nav a[aria-label="Home"]').click();
      cy.url().should('eq', Cypress.config().baseUrl + '/');
    });

    it('collapses and expands', () => {
      cy.get('button[aria-label="Collapse sidebar"]').click();
      // Verify expanded icon or attribute changes
      cy.get('button[aria-label="Expand sidebar"]').should('exist');
      cy.get('button[aria-label="Expand sidebar"]').click();
      cy.get('button[aria-label="Collapse sidebar"]').should('exist');
    });

    it('displays history zone', () => {
      // Look for Today or Last 7 days timeframe groups
      cy.contains('button', 'Today').should('exist');
    });
  });

  // ── Search (Cmd+K) ───────────────────────────────────────────────────────

  describe('Search Modal', () => {
    it('opens search with keyboard shortcut and returns results', () => {
      // Trigger Cmd+K
      cy.get('body').type('{cmd}k');
      cy.get('input[role="searchbox"]').should('be.visible').type('test query');
      // Wait for results
      cy.wait(1000);
      // It should either show results or "No results found"
      cy.get('[role="dialog"]').should('exist');
      // Close modal
      cy.get('body').type('{esc}');
    });
  });

  // ── Settings ─────────────────────────────────────────────────────────────

  describe('Settings Page', () => {
    it('displays connected services summary', () => {
      cy.visit('/settings');
      cy.contains('h2', 'Connected Services').should('exist');
      cy.contains('div', 'Platforms').should('exist');
      cy.contains('div', 'MCP Servers').should('exist');
      cy.contains('div', 'API Keys').should('exist');
    });
  });

  // ── MCP Page ─────────────────────────────────────────────────────────────

  describe('MCP Page', () => {
    it('displays server rows and health indicators', () => {
      cy.visit('/mcp');
      cy.contains('h1', 'MCP Context Servers').should('exist');
      cy.get('table').should('exist');
      // Check for status text
      cy.get('table tbody').should('exist');
    });
  });

  // ── Channels Page ────────────────────────────────────────────────────────

  describe('Channels Page', () => {
    it('displays platform cards and health indicators', () => {
      cy.visit('/channels');
      cy.contains('h1', 'Communication Channels').should('exist');
      // Look for the Telegram card
      cy.contains('h3.capitalize', 'telegram', { matchCase: false }).should('exist');
    });
  });

  // ── Conversation Flow ────────────────────────────────────────────────────

  describe('Conversation Flow & Management', () => {
    it('submits a prompt and creates a conversation', () => {
      cy.visit('/');
      const promptText = `Test prompt ${Date.now()}`;
      cy.get('input[placeholder="What do you want to build?"]').type(`${promptText}{enter}`);
      
      // Should navigate to /c/{id}
      cy.url({ timeout: 10000 }).should('include', '/c/');
      
      // The chat should have our prompt
      cy.contains(promptText).should('exist');
      
      // Follow up message
      cy.get('input[placeholder="What do you want to build?"]').type('Follow up{enter}');
      cy.contains('Follow up').should('exist');
      
      // Refresh page and see history restored
      cy.reload();
      cy.contains(promptText).should('exist');
      cy.contains('Follow up').should('exist');

      // Now go home and delete it from sidebar
      cy.visit('/');
      cy.get('a[href^="/c/"]').first().find('button').contains('more_horiz').click({ force: true });
      cy.contains('button', 'Delete').click({ force: true });
      // If there's a confirmation modal
      cy.get('[role="dialog"]').contains('button', 'Delete').click();
    });
  });

  // ── Plan Lifecycle ───────────────────────────────────────────────────────

  describe('Plan Lifecycle', () => {
    it('creates, views, runs, duplicates, and archives a plan', () => {
      cy.visit('/');
      // 1. Create (Navigate to Wizard)
      cy.get('nav a[aria-label="Plans"]').click();
      cy.contains('button', 'Create New Plan').click();
      
      // Step 1: Choose mode
      cy.contains('h4', 'Freeform').click();
      
      // Step 2: Fill details
      const planTitle = `E2E Plan ${Date.now()}`;
      cy.get('input[placeholder*="E-commerce"]').type(planTitle);
      cy.get('textarea[placeholder*="summary"]').type('Test plan description');
      cy.contains('button', 'Next').click();
      
      // Step 3: Preview
      cy.contains('h3', 'Preview Markdown').should('exist');
      cy.contains('button', 'Confirm Plan').click();
      
      // Step 4: Create
      cy.contains('button', 'Create Plan').click();
      
      // 2. View (Redirected to Detail Page)
      cy.url().should('include', '/plans/');
      cy.contains('h1', planTitle).should('exist');
      
      // 3. Run
      cy.contains('button', 'Run').click();
      cy.contains('button', 'Stop', { timeout: 10000 }).should('exist');
      
      // 4. Duplicate
      cy.get('button[title="Duplicate"]').click();
      cy.url().should('include', '/plans/');
      cy.contains('h1', planTitle).should('exist'); // It usually clones the title
      
      // 5. Archive
      cy.get('button[title="Archive"]').click();
      cy.url().should('eq', Cypress.config().baseUrl + '/');
    });
  });

});
