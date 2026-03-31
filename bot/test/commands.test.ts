import { expect } from 'chai';
import sinon from 'sinon';
import api from '../src/api';
import * as sessions from '../src/sessions';
import { routeCommand, routeCallback, handleStatefulText, cmdHelp } from '../src/commands';

describe('commands', () => {
  let sandbox: sinon.SinonSandbox;

  beforeEach(() => {
    sandbox = sinon.createSandbox();
    sessions.clearSession('u1', 'telegram');
    sessions.clearSession('u1', 'discord');
  });

  afterEach(() => {
    sandbox.restore();
  });

  // ── Fixtures ────────────────────────────────────────────────────

  const MOCK_ROOMS = {
    rooms: [
      { room_id: 'room-1', status: 'passed', message_count: 10, epic_ref: 'E-1' },
      { room_id: 'room-2', status: 'engineering', message_count: 5, epic_ref: 'E-2' },
      { room_id: 'room-3', status: 'failed-final', message_count: 3, epic_ref: 'E-3' },
    ],
    summary: { total: 3, passed: 1, engineering: 1, failed_final: 1, pending: 0, qa_review: 0, fixing: 0 },
  };

  const MOCK_PLANS = {
    plans: [
      { plan_id: 'p1', title: 'Auth System', status: 'launched', epic_count: 3 },
      { plan_id: 'p2', title: 'Dashboard UI', status: 'draft', epic_count: 2 },
    ],
    count: 2,
  };

  const MOCK_STATS = {
    total_plans: { value: 2 },
    active_epics: { value: 5 },
    completion_rate: { value: 33.3 },
    escalations_pending: { value: 0 },
  };

  // ── Menu commands (pure, no API) ─────────────────────────────

  describe('routeCommand — menu', () => {
    it('returns menu with 3 category buttons', async () => {
      const [resp] = await routeCommand('u1', 'telegram', 'menu');
      expect(resp.buttons).to.have.lengthOf(3);
      const data = resp.buttons!.flat().map(b => b.callbackData);
      expect(data).to.include('menu:cat:monitoring');
      expect(data).to.include('menu:cat:plans');
      expect(data).to.include('menu:cat:system');
    });
  });

  describe('routeCommand — help', () => {
    it('returns help text with all commands listed', async () => {
      const [resp] = await routeCommand('u1', 'telegram', 'help');
      expect(resp.text).to.include('/menu');
      expect(resp.text).to.include('/draft');
      expect(resp.text).to.include('/dashboard');
      expect(resp.text).to.include('/status');
    });

    it('start also returns help', async () => {
      const [resp] = await routeCommand('u1', 'telegram', 'start');
      expect(resp.text).to.include('/menu');
    });
  });

  describe('routeCommand — unknown', () => {
    it('returns unknown command message', async () => {
      const [resp] = await routeCommand('u1', 'telegram', 'nonexistent');
      expect(resp.text).to.include('Unknown command');
    });
  });

  // ── Monitoring commands (require API stubs) ───────────────────

  describe('routeCommand — dashboard', () => {
    it('renders dashboard with room counts', async () => {
      sandbox.stub(api, 'getRooms').resolves(MOCK_ROOMS);

      const [resp] = await routeCommand('u1', 'telegram', 'dashboard');
      expect(resp.text).to.include('COMMAND CENTER');
      expect(resp.text).to.include('ONLINE');
    });

    it('shows zeros when no rooms exist', async () => {
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      const [resp] = await routeCommand('u1', 'telegram', 'dashboard');
      expect(resp.text).to.include('0');
    });
  });

  describe('routeCommand — status', () => {
    it('lists all rooms with status', async () => {
      sandbox.stub(api, 'getRooms').resolves(MOCK_ROOMS);

      const [resp] = await routeCommand('u1', 'telegram', 'status');
      expect(resp.text).to.include('room-1');
      expect(resp.text).to.include('room-2');
      expect(resp.text).to.include('PASSED');
    });

    it('returns "No War-Rooms" when empty', async () => {
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      const [resp] = await routeCommand('u1', 'telegram', 'status');
      expect(resp.text).to.include('No War-Rooms');
    });

    it('shows error on API failure', async () => {
      sandbox.stub(api, 'getRooms').resolves({ error: 'connection refused', rooms: [], summary: {} });

      const [resp] = await routeCommand('u1', 'telegram', 'status');
      expect(resp.text).to.include('connection refused');
    });
  });

  describe('routeCommand — errors', () => {
    it('lists failed rooms', async () => {
      sandbox.stub(api, 'getRooms').resolves(MOCK_ROOMS);
      sandbox.stub(api, 'getRoomChannel').resolves([
        { type: 'error', body: 'Something went wrong in deployment' },
      ]);

      const [resp] = await routeCommand('u1', 'telegram', 'errors');
      expect(resp.text).to.include('room-3');
      expect(resp.text).to.include('FAILED-FINAL');
    });

    it('returns stable message when no errors', async () => {
      sandbox.stub(api, 'getRooms').resolves({ rooms: [{ room_id: 'r1', status: 'passed' }], summary: {} } as any);

      const [resp] = await routeCommand('u1', 'telegram', 'errors');
      expect(resp.text).to.include('stable');
    });
  });

  describe('routeCommand — compact', () => {
    it('shows latest messages from active rooms', async () => {
      sandbox.stub(api, 'getRooms').resolves(MOCK_ROOMS);
      sandbox.stub(api, 'getRoomChannel').resolves([
        { from: 'engineer', body: 'Working on feature X' },
      ]);

      const [resp] = await routeCommand('u1', 'telegram', 'compact');
      expect(resp.text).to.include('room-2');
      expect(resp.text).to.include('Working on feature X');
    });
  });

  // ── Plan commands ─────────────────────────────────────────────

  describe('routeCommand — plans', () => {
    it('lists all plans', async () => {
      sandbox.stub(api, 'getPlans').resolves(MOCK_PLANS);

      const [resp] = await routeCommand('u1', 'telegram', 'plans');
      expect(resp.text).to.include('Auth System');
      expect(resp.text).to.include('Dashboard UI');
      expect(resp.text).to.include('p1');
    });

    it('returns "No plans" when empty', async () => {
      sandbox.stub(api, 'getPlans').resolves({ plans: [], count: 0 });

      const [resp] = await routeCommand('u1', 'telegram', 'plans');
      expect(resp.text).to.include('No plans');
    });
  });

  describe('routeCommand — skills', () => {
    it('lists skills with tags', async () => {
      sandbox.stub(api, 'getSkills').resolves([
        { name: 'code-review', tags: ['qa', 'review'] },
        { name: 'deploy', tags: [] },
      ]);

      const [resp] = await routeCommand('u1', 'telegram', 'skills');
      expect(resp.text).to.include('code-review');
      expect(resp.text).to.include('qa, review');
      expect(resp.text).to.include('General');
    });
  });

  describe('routeCommand — usage', () => {
    it('returns stats report', async () => {
      sandbox.stub(api, 'getStats').resolves(MOCK_STATS);

      const [resp] = await routeCommand('u1', 'telegram', 'usage');
      expect(resp.text).to.include('STATS REPORT');
      expect(resp.text).to.include('33.3%');
    });
  });

  // ── System commands ────────────────────────────────────────────

  describe('routeCommand — new', () => {
    it('wipes war-rooms and returns confirmation', async () => {
      sandbox.stub(api, 'resetRooms').resolves({ status: 'ok' });

      const [resp] = await routeCommand('u1', 'telegram', 'new');
      expect(resp.text).to.include('Cleaned up');
    });

    it('handles error during wipe', async () => {
      sandbox.stub(api, 'resetRooms').resolves({ _error: 'permission denied' });

      const [resp] = await routeCommand('u1', 'telegram', 'new');
      expect(resp.text).to.include('Failed');
    });
  });

  describe('routeCommand — restart', () => {
    it('calls stop endpoint and returns confirmation', async () => {
      sandbox.stub(api, 'stopDashboard').resolves({ status: 'stopped' });

      const [resp] = await routeCommand('u1', 'telegram', 'restart');
      expect(resp.text).to.include('Restarting');
    });
  });

  // ── Plan selection menus ──────────────────────────────────────

  describe('routeCommand — edit', () => {
    it('returns plan selection buttons', async () => {
      sandbox.stub(api, 'getPlans').resolves(MOCK_PLANS);

      const [resp] = await routeCommand('u1', 'telegram', 'edit');
      expect(resp.buttons).to.be.an('array');
      expect(resp.buttons!.length).to.be.greaterThan(0);
      const data = resp.buttons!.flat().map(b => b.callbackData);
      expect(data[0]).to.match(/^menu:edit:/);
    });

    it('returns text when no plans', async () => {
      sandbox.stub(api, 'getPlans').resolves({ plans: [], count: 0 });

      const [resp] = await routeCommand('u1', 'telegram', 'edit');
      expect(resp.text).to.include('No plans');
      expect(resp.buttons).to.be.undefined;
    });
  });

  describe('routeCommand — viewplan', () => {
    it('returns plan selection buttons', async () => {
      sandbox.stub(api, 'getPlans').resolves(MOCK_PLANS);

      const [resp] = await routeCommand('u1', 'telegram', 'viewplan');
      expect(resp.buttons).to.be.an('array');
      const data = resp.buttons!.flat().map(b => b.callbackData);
      expect(data[0]).to.match(/^menu:view:/);
    });
  });

  describe('routeCommand — startplan', () => {
    it('returns plan selection buttons with launch prefix', async () => {
      sandbox.stub(api, 'getPlans').resolves(MOCK_PLANS);

      const [resp] = await routeCommand('u1', 'telegram', 'startplan');
      expect(resp.buttons).to.be.an('array');
      const data = resp.buttons!.flat().map(b => b.callbackData);
      expect(data[0]).to.match(/^menu:launch_prompt:/);
    });
  });

  // ── Session commands ──────────────────────────────────────────

  describe('routeCommand — cancel', () => {
    it('clears session and returns confirmation', async () => {
      sessions.setMode('u1', 'telegram', 'editing');
      sessions.setPlan('u1', 'telegram', 'p1');

      const [resp] = await routeCommand('u1', 'telegram', 'cancel');
      expect(resp.text).to.include('cancelled');

      const s = sessions.getSession('u1', 'telegram');
      expect(s.mode).to.equal('idle');
      expect(s.activePlanId).to.be.null;
    });
  });

  describe('routeCommand — draft', () => {
    it('sets awaiting_idea mode when no args', async () => {
      const [resp] = await routeCommand('u1', 'telegram', 'draft', '');
      expect(resp.text).to.include('idea');
      expect(sessions.getSession('u1', 'telegram').mode).to.equal('awaiting_idea');
    });

    it('calls AI refinement when idea provided', async () => {
      sandbox.stub(api, 'refinePlan').resolves({
        plan: '# Plan: Auth',
        explanation: 'Created auth plan',
      });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'auth-1234' });

      const responses = await routeCommand('u1', 'telegram', 'draft', 'Build auth system');
      expect(responses.length).to.be.at.least(2);
      expect(responses[0].text).to.include('Drafting');
      const hasDrafted = responses.some(r => r.text.includes('Plan Drafted'));
      expect(hasDrafted).to.be.true;
      const hasContent = responses.some(r => r.text.includes('Plan: Auth'));
      expect(hasContent).to.be.true;
    });

    it('handles API error during draft', async () => {
      sandbox.stub(api, 'refinePlan').resolves({ _error: 'AI unavailable' });

      const responses = await routeCommand('u1', 'telegram', 'draft', 'Some idea');
      const hasError = responses.some(r => r.text.includes('Failed'));
      expect(hasError).to.be.true;
    });
  });

  // ── Cross-platform ────────────────────────────────────────────

  describe('cross-platform', () => {
    it('same commands work for discord platform', async () => {
      sandbox.stub(api, 'getRooms').resolves(MOCK_ROOMS);

      const [resp] = await routeCommand('u1', 'discord', 'dashboard');
      expect(resp.text).to.include('COMMAND CENTER');
    });

    it('cancel clears discord session, not telegram', async () => {
      sessions.setMode('u1', 'telegram', 'editing');
      sessions.setMode('u1', 'discord', 'drafting');

      await routeCommand('u1', 'discord', 'cancel');

      expect(sessions.getSession('u1', 'discord').mode).to.equal('idle');
      expect(sessions.getSession('u1', 'telegram').mode).to.equal('editing');
    });
  });

  // ── Callback routing ──────────────────────────────────────────

  describe('routeCallback', () => {
    it('menu:main returns main menu', async () => {
      const [resp] = await routeCallback('u1', 'telegram', 'menu:main');
      expect(resp.buttons).to.have.lengthOf(3);
    });

    it('menu:cat:monitoring returns monitoring submenu', async () => {
      const [resp] = await routeCallback('u1', 'telegram', 'menu:cat:monitoring');
      const data = resp.buttons!.flat().map(b => b.callbackData);
      expect(data).to.include('cmd:dashboard');
    });

    it('menu:cat:plans returns plans submenu', async () => {
      const [resp] = await routeCallback('u1', 'telegram', 'menu:cat:plans');
      const data = resp.buttons!.flat().map(b => b.callbackData);
      expect(data).to.include('cmd:draft_prompt');
    });

    it('menu:cat:system returns system submenu', async () => {
      const [resp] = await routeCallback('u1', 'telegram', 'menu:cat:system');
      const data = resp.buttons!.flat().map(b => b.callbackData);
      expect(data).to.include('cmd:usage');
    });

    it('cmd:dashboard dispatches to dashboard command', async () => {
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      const [resp] = await routeCallback('u1', 'telegram', 'cmd:dashboard');
      expect(resp.text).to.include('COMMAND CENTER');
    });

    it('cmd:draft_prompt returns draft instructions', async () => {
      const [resp] = await routeCallback('u1', 'telegram', 'cmd:draft_prompt');
      expect(resp.text).to.include('/draft');
    });

    it('menu:view:p1 views a plan', async () => {
      sandbox.stub(api, 'getPlan').resolves({ plan_id: 'p1', content: '# My Plan' });

      const [resp] = await routeCallback('u1', 'telegram', 'menu:view:p1');
      expect(resp.text).to.include('My Plan');
    });

    it('menu:edit:p1 enters editing mode', async () => {
      const [resp] = await routeCallback('u1', 'telegram', 'menu:edit:p1');
      expect(resp.text).to.include('Editing Mode');
      expect(sessions.getSession('u1', 'telegram').mode).to.equal('editing');
      expect(sessions.getSession('u1', 'telegram').activePlanId).to.equal('p1');
    });

    it('menu:launch_prompt:p1 shows confirmation', async () => {
      const [resp] = await routeCallback('u1', 'telegram', 'menu:launch_prompt:p1');
      expect(resp.text).to.include('Confirm Launch');
      expect(resp.buttons).to.be.an('array');
      const data = resp.buttons!.flat().map(b => b.callbackData);
      expect(data).to.include('menu:launch_confirm:p1');
    });

    it('menu:launch_confirm:p1 launches the plan', async () => {
      sandbox.stub(api, 'getPlan').resolves({ plan_id: 'p1', content: '# Plan\n## Epic: E1' });
      sandbox.stub(api, 'launchPlan').resolves({ status: 'launched' });

      const responses = await routeCallback('u1', 'telegram', 'menu:launch_confirm:p1');
      const hasLaunch = responses.some(r => r.text.includes('Launched'));
      expect(hasLaunch).to.be.true;
    });

    it('menu:launch_cancel returns cancellation', async () => {
      const [resp] = await routeCallback('u1', 'telegram', 'menu:launch_cancel');
      expect(resp.text).to.include('cancelled');
    });

    it('menu:plans returns plans list', async () => {
      sandbox.stub(api, 'getPlans').resolves(MOCK_PLANS);

      const [resp] = await routeCallback('u1', 'telegram', 'menu:plans');
      expect(resp.text).to.include('Auth System');
    });

    it('returns empty for unknown callback', async () => {
      const responses = await routeCallback('u1', 'telegram', 'unknown:data');
      expect(responses).to.deep.equal([]);
    });
  });

  // ── Stateful text handling ────────────────────────────────────

  describe('handleStatefulText', () => {
    it('drafts plan when in awaiting_idea mode', async () => {
      sessions.setMode('u1', 'telegram', 'awaiting_idea');
      sessions.setPlan('u1', 'telegram', 'new');

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Draft', explanation: 'Created' });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'test-1234' });

      const responses = await handleStatefulText('u1', 'telegram', 'Build a todo app');
      expect(responses.length).to.be.at.least(2);
      expect(responses[0].text).to.include('Drafting');
    });

    it('refines plan when in editing mode', async () => {
      sessions.setMode('u1', 'telegram', 'editing');
      sessions.setPlan('u1', 'telegram', 'p1');

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Updated', explanation: 'Refined' });
      sandbox.stub(api, 'savePlan').resolves({ status: 'saved' });

      const responses = await handleStatefulText('u1', 'telegram', 'Add more tests');
      expect(responses[0].text).to.include('Refining');
      const hasUpdated = responses.some(r => r.text.includes('Updated'));
      expect(hasUpdated).to.be.true;
    });

    it('appends to chat history during editing', async () => {
      sessions.setMode('u1', 'telegram', 'editing');
      sessions.setPlan('u1', 'telegram', 'p1');

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# V2' });
      sandbox.stub(api, 'savePlan').resolves({});

      await handleStatefulText('u1', 'telegram', 'First instruction');
      await handleStatefulText('u1', 'telegram', 'Second instruction');

      const s = sessions.getSession('u1', 'telegram');
      expect(s.chatHistory).to.have.lengthOf(4); // 2 user + 2 assistant
    });

    it('returns empty when session has no plan', async () => {
      sessions.setMode('u1', 'telegram', 'editing');
      // No plan set

      const responses = await handleStatefulText('u1', 'telegram', 'hello');
      expect(responses).to.deep.equal([]);
    });

    it('handles API error during refine', async () => {
      sessions.setMode('u1', 'telegram', 'editing');
      sessions.setPlan('u1', 'telegram', 'p1');

      sandbox.stub(api, 'refinePlan').resolves({ _error: 'Server error' });

      const responses = await handleStatefulText('u1', 'telegram', 'Fix something');
      const hasError = responses.some(r => r.text.includes('Failed'));
      expect(hasError).to.be.true;
    });
  });
});
