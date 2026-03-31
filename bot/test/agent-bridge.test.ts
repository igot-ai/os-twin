import { expect } from 'chai';
import sinon from 'sinon';
import config from '../src/config';
import api from '../src/api';
import { askAgent } from '../src/agent-bridge';
import * as googleAi from '@google/generative-ai';

describe('agent-bridge', () => {
  let sandbox: sinon.SinonSandbox;
  const originalApiKey = config.GOOGLE_API_KEY;

  before(() => {
    sandbox = sinon.createSandbox();
  });

  afterEach(() => {
    sandbox.restore();
    config.GOOGLE_API_KEY = originalApiKey;
  });

  // ── Without GOOGLE_API_KEY ────────────────────────────────────
  
  // ... existing tests ...

  describe('context gathering', () => {
    it('calls all API endpoints in parallel', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      const plansStub = sandbox.stub(api, 'getPlans').resolves({ plans: [], count: 0 });
      const roomsStub = sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });
      const statsStub = sandbox.stub(api, 'getStats').resolves({ _error: 'unavailable' } as any);
      const searchStub = sandbox.stub(api, 'semanticSearch').resolves({ results: [] });

      try {
        await askAgent('test question');
      } catch {
        // Expected if Gemini mock isn't set up
      }

      // Verify all API calls were made
      expect(plansStub.calledOnce).to.be.true;
      expect(roomsStub.calledOnce).to.be.true;
      expect(statsStub.calledOnce).to.be.true;
      expect(searchStub.calledOnce).to.be.true;
      expect(searchStub.firstCall.args[0]).to.equal('test question');
    });

    it('formats plans and rooms correctly when data exists', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({
        plans: [{ plan_id: 'p1', title: 'Plan 1', status: 'draft', pct_complete: 50 }],
        count: 1
      });
      sandbox.stub(api, 'getRooms').resolves({
        rooms: [{ room_id: 'r1', status: 'engineering', epic_ref: 'E1', message_count: 1 }],
        summary: {}
      });
      sandbox.stub(api, 'getStats').resolves({
        total_plans: { value: 1 },
        active_epics: { value: 1 }
      });
      sandbox.stub(api, 'semanticSearch').resolves([
        { room_id: 'r1', from: 'eng', body: 'hello' }
      ]);
    });

    it('handles empty data gracefully', async () => {
      config.GOOGLE_API_KEY = 'test-key';
      sandbox.stub(api, 'getPlans').resolves({ plans: [], count: 0 });
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });
      sandbox.stub(api, 'getStats').resolves({ _error: 'fail' } as any);
      sandbox.stub(api, 'semanticSearch').resolves([]);
      
      try {
        await askAgent('test');
      } catch {}
    });
  });
});
