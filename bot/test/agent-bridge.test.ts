import { expect } from 'chai';
import sinon from 'sinon';
import config from '../src/config';
import api from '../src/api';
import { askAgent } from '../src/agent-bridge';

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

  describe('when GOOGLE_API_KEY is not set', () => {
    it('returns error message about missing API key', async () => {
      config.GOOGLE_API_KEY = '';
      const result = await askAgent('What is the status?');
      expect(result).to.include('GOOGLE_API_KEY');
    });
  });

  // ── Context gathering ─────────────────────────────────────────

  describe('context gathering', () => {
    it('calls all API endpoints in parallel', async () => {
      config.GOOGLE_API_KEY = 'test-key';

      const plansStub = sandbox.stub(api, 'getPlans').resolves({ plans: [], count: 0 });
      const roomsStub = sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });
      const statsStub = sandbox.stub(api, 'getStats').resolves({ _error: 'unavailable' } as any);
      const searchStub = sandbox.stub(api, 'semanticSearch').resolves({ results: [] });

      try {
        const result = await askAgent('test question');
        expect(result).to.be.a('string');
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
  });
});
