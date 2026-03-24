/**
 * Server State (for Mock API)
 * Holds in-memory copies of mock data to support mutation during the session.
 */

import { 
  mockStats, 
  mockPlans, 
  mockEpics, 
  mockMessages, 
  mockLifecycle, 
  mockRoles, 
  mockSkills, 
  mockNotifications, 
  mockModels,
  mockDAG
} from './mock-data';

// Initialize in-memory state
export const state = {
  stats: { ...mockStats },
  plans: [...mockPlans],
  epics: [...mockEpics],
  messages: [...mockMessages],
  lifecycle: { ...mockLifecycle },
  roles: [...mockRoles],
  skills: [...mockSkills],
  notifications: [...mockNotifications],
  models: [...mockModels],
  dag: { ...mockDAG },
};

// Simple update helpers
export const updatePlan = (id: string, updates: Record<string, unknown>) => {
  const index = state.plans.findIndex(p => p.plan_id === id);
  if (index !== -1) {
    state.plans[index] = { ...state.plans[index], ...updates, updated_at: new Date().toISOString() };
    return state.plans[index];
  }
  return null;
};

export const updateEpic = (ref: string, updates: Record<string, unknown>) => {
  const index = state.epics.findIndex(e => e.epic_ref === ref);
  if (index !== -1) {
    state.epics[index] = { ...state.epics[index], ...updates };
    return state.epics[index];
  }
  return null;
};
