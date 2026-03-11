import './commands';

// Suppress uncaught exceptions from SSE reconnects during test teardown
Cypress.on('uncaught:exception', (err) => {
  // EventSource reconnect errors are expected during server resets
  if (err.message.includes('EventSource') || err.message.includes('NetworkError')) {
    return false;
  }
});
