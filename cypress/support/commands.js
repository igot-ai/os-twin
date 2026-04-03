// ─── Agent OS Custom Commands ────────────────────────────────────────────────

/**
 * cy.agentPost(room, { from_, to, type, ref, body })
 * Post a message to a war-room channel via the node task.
 */
Cypress.Commands.add('agentPost', (room, { from_, to, type, ref, body }) => {
  cy.task('postMessage', { room, from_, to, type, ref, body });
});

/**
 * cy.setRoomStatus(room, status)
 * Directly write a status file for a room.
 */
Cypress.Commands.add('setRoomStatus', (room, status) => {
  cy.task('setRoomStatus', { room, status });
});

/**
 * cy.waitForRoom(roomId, options)
 * Retry cy.request until the room appears in /api/rooms with the given status.
 */
Cypress.Commands.add('waitForRoom', (roomId, { status, timeout = 15000 } = {}) => {
  const start = Date.now();
  const check = () => {
    return cy.request('/api/rooms').then(({ body }) => {
      const room = (body.rooms || []).find(r => r.room_id === roomId);
      if (room && (!status || room.status === status)) return room;
      if (Date.now() - start > timeout) throw new Error(`Timeout waiting for ${roomId} status=${status}`);
      return cy.wait(500).then(check);
    });
  };
  return check();
});

/**
 * cy.launchPlan(planText)
 * Clear the textarea, type a plan, and click LAUNCH.
 */
Cypress.Commands.add('launchPlan', (planText) => {
  cy.get('#plan-input').clear().type(planText, { delay: 0 });
  cy.get('#launch-btn').click();
});

/**
 * cy.advanceRoom(room, taskRef)
 * Advance a room through the full pipeline: done → pass → passed.
 * Used in tests to simulate mock engineer + QA without real CLI tools.
 */
Cypress.Commands.add('advanceRoom', (room, taskRef) => {
  cy.agentPost(room, {
    from_: 'engineer', to: 'manager', type: 'done', ref: taskRef,
    body: `[test] ${taskRef} complete`,
  });
  cy.setRoomStatus(room, 'review');
  cy.wait(600);
  cy.agentPost(room, {
    from_: 'qa', to: 'manager', type: 'pass', ref: taskRef,
    body: `VERDICT: PASS. ${taskRef} verified by test suite.`,
  });
  cy.setRoomStatus(room, 'passed');
});
