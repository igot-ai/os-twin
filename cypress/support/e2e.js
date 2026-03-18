import './commands';

// Suppress uncaught exceptions from SSE reconnects during test teardown
Cypress.on('uncaught:exception', (err) => {
  // EventSource reconnect errors are expected during server resets
  if (err.message.includes('EventSource') || err.message.includes('NetworkError')) {
    return false;
  }
});

let authToken = null;

before(() => {
  // Skipping global auth for simple pipeline test
});

beforeEach(() => {
  if (authToken) {
    window.localStorage.setItem('agent_os_token', authToken);
  }
});

Cypress.Commands.overwrite('request', (originalFn, ...args) => {
  let options = {};
  if (typeof args[0] === 'string') {
    options = { url: args[0] };
    if (args.length > 1) {
      Object.assign(options, args[1]);
    }
  } else {
    options = { ...args[0] };
  }

  // Don't add auth header if we are fetching the token itself
  if (options.url && !options.url.includes('/api/auth/token') && authToken) {
    options.headers = options.headers || {};
    options.headers['Authorization'] = `Bearer ${authToken}`;
  }

  return originalFn(options);
});
