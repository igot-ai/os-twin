import { expect } from 'chai';
import { getSession, clearSession, setMode, setPlan } from '../src/sessions';

describe('sessions', () => {
  beforeEach(() => {
    clearSession('u1', 'telegram');
    clearSession('u1', 'discord');
    clearSession('u2', 'telegram');
  });

  afterEach(() => {
    clearSession('u1', 'telegram');
    clearSession('u1', 'discord');
    clearSession('u2', 'telegram');
  });

  describe('getSession', () => {
    it('creates a new session with default values', () => {
      const s = getSession('u1', 'telegram');
      expect(s.userId).to.equal('u1');
      expect(s.platform).to.equal('telegram');
      expect(s.mode).to.equal('idle');
      expect(s.activePlanId).to.be.null;
      expect(s.chatHistory).to.deep.equal([]);
      expect(s.lastActivity).to.be.a('number');
    });

    it('returns the same session on subsequent calls', () => {
      const s1 = getSession('u1', 'telegram');
      s1.mode = 'editing';
      const s2 = getSession('u1', 'telegram');
      expect(s2.mode).to.equal('editing');
    });

    it('defaults platform to telegram', () => {
      const s = getSession('u1');
      expect(s.platform).to.equal('telegram');
    });

    it('coerces userId to string', () => {
      const s = getSession(123, 'telegram');
      expect(s.userId).to.equal('123');
    });
  });

  describe('platform isolation', () => {
    it('keeps separate sessions per platform', () => {
      setMode('u1', 'telegram', 'editing');
      setMode('u1', 'discord', 'drafting');

      expect(getSession('u1', 'telegram').mode).to.equal('editing');
      expect(getSession('u1', 'discord').mode).to.equal('drafting');
    });

    it('clearing one platform does not affect the other', () => {
      setMode('u1', 'telegram', 'editing');
      setMode('u1', 'discord', 'drafting');

      clearSession('u1', 'telegram');

      expect(getSession('u1', 'telegram').mode).to.equal('idle');
      expect(getSession('u1', 'discord').mode).to.equal('drafting');
    });
  });

  describe('setMode', () => {
    it('changes the session mode', () => {
      setMode('u1', 'telegram', 'editing');
      expect(getSession('u1', 'telegram').mode).to.equal('editing');
    });

    it('updates lastActivity', () => {
      const s = getSession('u1', 'telegram');
      const before = s.lastActivity;
      setMode('u1', 'telegram', 'drafting');
      expect(getSession('u1', 'telegram').lastActivity).to.be.at.least(before);
    });
  });

  describe('setPlan', () => {
    it('sets the active plan ID', () => {
      setPlan('u1', 'telegram', 'plan-abc');
      expect(getSession('u1', 'telegram').activePlanId).to.equal('plan-abc');
    });
  });

  describe('clearSession', () => {
    it('resets all session fields', () => {
      setMode('u1', 'telegram', 'editing');
      setPlan('u1', 'telegram', 'plan-abc');
      getSession('u1', 'telegram').chatHistory.push({ role: 'user', content: 'hello' });

      clearSession('u1', 'telegram');

      const s = getSession('u1', 'telegram');
      expect(s.mode).to.equal('idle');
      expect(s.activePlanId).to.be.null;
      expect(s.chatHistory).to.deep.equal([]);
    });
  });

  describe('session timeout', () => {
    it('resets session after 30 min of inactivity', () => {
      const s = getSession('u1', 'telegram');
      s.mode = 'editing';
      s.activePlanId = 'plan-old';
      // Simulate 31 minutes ago
      s.lastActivity = Date.now() - (31 * 60 * 1000);

      const fresh = getSession('u1', 'telegram');
      expect(fresh.mode).to.equal('idle');
      expect(fresh.activePlanId).to.be.null;
    });

    it('does not reset if within 30 min', () => {
      const s = getSession('u1', 'telegram');
      s.mode = 'editing';
      s.lastActivity = Date.now() - (29 * 60 * 1000);

      const same = getSession('u1', 'telegram');
      expect(same.mode).to.equal('editing');
    });
  });
});
