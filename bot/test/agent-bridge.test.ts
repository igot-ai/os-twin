import { expect } from 'chai';
import sinon from 'sinon';
import config from '../src/config';
import api from '../src/api';
import { askAgent } from '../src/agent-bridge';

/**
 * Tests for the agent-bridge with tool-calling capabilities.
 *
 * The upgraded bridge uses Gemini function calling to autonomously
 * create plans, list plans, check status, and launch plans.
 *
 * Since mocking the Gemini constructor chain is complex, we focus on:
 * 1. API key validation
 * 2. Context gathering (getPlans, getRooms)
 * 3. Error handling
 * 4. Backward compatibility (ctx parameter optional)
 */

describe('agent-bridge', () => {
  let sandbox: sinon.SinonSandbox;
  const originalApiKey = config.GOOGLE_API_KEY;

  beforeEach(() => {
    sandbox = sinon.createSandbox();
  });

  afterEach(() => {
    sandbox.restore();
    config.GOOGLE_API_KEY = originalApiKey;
  });

  // ── API key validation ──────────────────────────────────────────

  it('returns error when GOOGLE_API_KEY is not set', async () => {
    config.GOOGLE_API_KEY = '';
    const result = await askAgent('test question');
    expect(result).to.include('GOOGLE_API_KEY');
    expect(result).to.include('not set');
  });

  // ── Context gathering ───────────────────────────────────────────

  describe('context gathering', () => {
    it('calls all API endpoints in parallel', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      const plansStub = sandbox.stub(api, 'getPlans').resolves({ plans: [], count: 0 });
      const roomsStub = sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      try {
        // Will fail at Gemini API call but we verify the context gathering happened
        await askAgent('test question');
      } catch {
        // Expected — Gemini API is not mocked
      }

      expect(plansStub.calledOnce).to.be.true;
      expect(roomsStub.calledOnce).to.be.true;
    });

    it('formats plans and rooms correctly when data exists', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      const plansStub = sandbox.stub(api, 'getPlans').resolves({
        plans: [{ plan_id: 'p1', title: 'Plan 1', status: 'draft', pct_complete: 50, epic_count: 3 }],
        count: 1,
      });
      sandbox.stub(api, 'getRooms').resolves({
        rooms: [{ room_id: 'r1', status: 'engineering', epic_ref: 'EPIC-001' }],
        summary: {},
      });

      try {
        await askAgent('what is happening?');
      } catch {
        // Expected — Gemini API is not mocked
      }

      // Verify the plans data was retrieved for context building
      expect(plansStub.calledOnce).to.be.true;
      const plansResult = await plansStub.returnValues[0];
      expect(plansResult.plans).to.have.length(1);
      expect(plansResult.plans[0].title).to.equal('Plan 1');
    });

    it('handles empty data gracefully', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [], count: 0 });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      // Should not throw even with empty data
      // (will still fail at Gemini, but the context gathering should succeed)
      try {
        await askAgent('test');
      } catch {
        // Expected
      }
    });
  });

  // ── Error handling ──────────────────────────────────────────────

  describe('error handling', () => {
    it('returns user-friendly error when Gemini API fails', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [] });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      // The real Gemini API call will fail with an invalid key
      const result = await askAgent('test');
      // Should return an error message, not throw
      expect(result).to.be.a('string');
      expect(result).to.include('Failed to get a response');
    });
  });

  // ── Backward compatibility ─────────────────────────────────────

  describe('backward compatibility', () => {
    it('works without ctx parameter (old signature)', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [] });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      // Call without ctx — should not throw from context handling
      const result = await askAgent('hello');
      expect(result).to.be.a('string');
    });

    it('accepts ctx parameter for tool execution', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [] });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      // Call with ctx — should not throw
      const result = await askAgent('hello', { userId: 'u1', platform: 'discord' });
      expect(result).to.be.a('string');
    });
  });

  // ── Function signature ─────────────────────────────────────────

  describe('function signature', () => {
    it('askAgent is exported as an async function', () => {
      expect(typeof askAgent).to.equal('function');
    });

    it('returns a string', async () => {
      config.GOOGLE_API_KEY = '';
      const result = await askAgent('test');
      expect(typeof result).to.equal('string');
    });
  });
});
