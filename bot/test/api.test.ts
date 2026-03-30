import { expect } from 'chai';
import sinon from 'sinon';
import api from '../src/api';

describe('api', () => {
  let fetchStub: sinon.SinonStub;

  before(() => {
    fetchStub = sinon.stub(global, 'fetch');
  });

  afterEach(() => {
    fetchStub.reset();
  });

  after(() => {
    fetchStub.restore();
  });

  function mockFetch(data: any, status = 200): void {
    fetchStub.resolves({
      ok: status >= 200 && status < 300,
      status,
      json: async () => data,
    });
  }

  function mockFetchError(message: string): void {
    fetchStub.rejects(new Error(message));
  }

  // ── getPlans ──────────────────────────────────────────────────

  describe('getPlans', () => {
    it('returns plans array on success', async () => {
      const plans = [
        { plan_id: 'p1', title: 'Plan One', status: 'draft', epic_count: 2 },
        { plan_id: 'p2', title: 'Plan Two', status: 'launched', epic_count: 5 },
      ];
      mockFetch({ plans, count: 2 });

      const result = await api.getPlans();
      expect(result.plans).to.have.lengthOf(2);
      expect(result.plans[0].plan_id).to.equal('p1');
      expect(result.count).to.equal(2);
    });

    it('returns empty plans on API error', async () => {
      mockFetch({}, 500);

      const result = await api.getPlans();
      expect(result.plans).to.deep.equal([]);
      expect(result.error).to.include('500');
    });

    it('returns empty plans when dashboard is unreachable', async () => {
      mockFetchError('Connection refused');

      const result = await api.getPlans();
      expect(result.plans).to.deep.equal([]);
      expect(result.error).to.include('unreachable');
    });
  });

  // ── getPlan ───────────────────────────────────────────────────

  describe('getPlan', () => {
    it('returns plan data on success', async () => {
      mockFetch({ plan_id: 'p1', content: '# Plan: Test', title: 'Test' });

      const result = await api.getPlan('p1');
      expect(result.plan_id).to.equal('p1');
      expect(result.content).to.include('Plan');
    });

    it('returns _error on 404', async () => {
      mockFetch({}, 404);

      const result = await api.getPlan('missing');
      expect(result._error).to.include('404');
    });
  });

  // ── getRooms ──────────────────────────────────────────────────

  describe('getRooms', () => {
    it('returns rooms and summary', async () => {
      const data = {
        rooms: [
          { room_id: 'room-1', status: 'passed', message_count: 10 },
          { room_id: 'room-2', status: 'engineering', message_count: 5 },
        ],
        summary: { total: 2, passed: 1, engineering: 1 },
      };
      mockFetch(data);

      const result = await api.getRooms();
      expect(result.rooms).to.have.lengthOf(2);
      expect(result.summary.total).to.equal(2);
    });

    it('returns empty on error', async () => {
      mockFetchError('timeout');

      const result = await api.getRooms();
      expect(result.rooms).to.deep.equal([]);
      expect(result.error).to.be.a('string');
    });
  });

  // ── refinePlan ────────────────────────────────────────────────

  describe('refinePlan', () => {
    it('sends correct request body', async () => {
      mockFetch({ plan: '# Plan', explanation: 'Added epics' });

      await api.refinePlan({
        message: 'Add auth epic',
        planContent: '# Old plan',
        planId: 'p1',
        chatHistory: [{ role: 'user', content: 'hello' }],
      });

      const [url, opts] = fetchStub.firstCall.args;
      expect(url).to.include('/api/plans/refine');
      const body = JSON.parse(opts.body);
      expect(body.message).to.equal('Add auth epic');
      expect(body.plan_content).to.equal('# Old plan');
      expect(body.plan_id).to.equal('p1');
      expect(body.chat_history).to.have.lengthOf(1);
    });
  });

  // ── launchPlan ────────────────────────────────────────────────

  describe('launchPlan', () => {
    it('sends plan content in request body', async () => {
      mockFetch({ status: 'launched', plan_id: 'p1' });

      await api.launchPlan('p1', '# Plan content');

      const [url, opts] = fetchStub.firstCall.args;
      expect(url).to.include('/api/run');
      const body = JSON.parse(opts.body);
      expect(body.plan).to.equal('# Plan content');
      expect(body.plan_id).to.equal('p1');
    });
  });

  // ── getSkills ─────────────────────────────────────────────────

  describe('getSkills', () => {
    it('returns skills array', async () => {
      mockFetch([{ name: 'skill1', tags: ['test'] }]);

      const result = await api.getSkills();
      expect(result).to.have.lengthOf(1);
      expect(result[0].name).to.equal('skill1');
    });

    it('returns empty array on error', async () => {
      mockFetchError('fail');

      const result = await api.getSkills();
      expect(result).to.deep.equal([]);
    });
  });

  // ── getStats ──────────────────────────────────────────────────

  describe('getStats', () => {
    it('returns stats object', async () => {
      const stats = {
        total_plans: { value: 3 },
        active_epics: { value: 5 },
        completion_rate: { value: 60.5 },
        escalations_pending: { value: 1 },
      };
      mockFetch(stats);

      const result = await api.getStats();
      expect(result.total_plans!.value).to.equal(3);
      expect(result.completion_rate!.value).to.equal(60.5);
    });
  });
});
