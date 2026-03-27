/// <reference types="cypress" />

context('Student CRM', () => {
  const studentName = 'John Doe';
  const studentEmail = 'john.doe@example.com';
  const sessionSummary = 'Test session summary';
  const sessionNotes = 'Test session notes';

  beforeEach(() => {
    cy.visit('/');
    // Assuming there is a way to reset the state before each test
    cy.task('resetAgentOS');
  });

  it('should create a new student', () => {
    cy.contains('New Student').click();
    cy.get('input[name="name"]').type(studentName);
    cy.get('input[name="email"]').type(studentEmail);
    cy.contains('Save').click();
  });

  it('should appear in the main student list', () => {
    // First create a student
    cy.contains('New Student').click();
    cy.get('input[name="name"]').type(studentName);
    cy.get('input[name="email"]').type(studentEmail);
    cy.contains('Save').click();

    // Now check if the student is in the list
    cy.contains('.student-list-item', studentName).should('exist');
    cy.contains('.student-list-item', studentEmail).should('exist');
  });

  it('should add a learning session for a student', () => {
    // First create a student
    cy.contains('New Student').click();
    cy.get('input[name="name"]').type(studentName);
    cy.get('input[name="email"]').type(studentEmail);
    cy.contains('Save').click();

    // Go to student detail page
    cy.contains('.student-list-item', studentName).click();

    // Add a learning session
    cy.contains('Add Learning Session').click();
    cy.get('input[name="summary"]').type(sessionSummary);
    cy.get('textarea[name="notes"]').type(sessionNotes);
    cy.contains('Save Session').click();

    // Verify the session is displayed
    cy.contains('.session-summary', sessionSummary).should('exist');
    cy.contains('.session-notes', sessionNotes).should('exist');
  });
});
