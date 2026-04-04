/**
 * Telegram bot integration tests.
 *
 * Tests the full flow: Telegram update → middleware → handler → command router → API → response.
 * Overrides Telegraf's callApi at the prototype level to capture outgoing messages.
 */

import { expect } from 'chai';
import sinon from 'sinon';
import config from '../src/config';
import api from '../src/api';
import * as sessions from '../src/sessions';
import { createTelegramBot } from '../src/telegram';

// ── Helpers ─────────────────────────────────────────────────────────

const FAKE_BOT_INFO = {
  id: 123456,
  is_bot: true,
  first_name: 'TestBot',
  username: 'test_bot',
  can_join_groups: true,
  can_read_all_group_messages: false,
  supports_inline_queries: false,
};

function makeCommandUpdate(text: string, chatId = 123) {
  const cmd = text.split(' ')[0];
  return {
    update_id: Math.floor(Math.random() * 100000),
    message: {
      message_id: Math.floor(Math.random() * 100000),
      from: { id: chatId, is_bot: false, first_name: 'TestUser' },
      chat: { id: chatId, type: 'private' as const },
      date: Math.floor(Date.now() / 1000),
      text,
      entities: [{ type: 'bot_command' as const, offset: 0, length: cmd.length }],
    },
  };
}

function makeTextUpdate(text: string, chatId = 123) {
  return {
    update_id: Math.floor(Math.random() * 100000),
    message: {
      message_id: Math.floor(Math.random() * 100000),
      from: { id: chatId, is_bot: false, first_name: 'TestUser' },
      chat: { id: chatId, type: 'private' as const },
      date: Math.floor(Date.now() / 1000),
      text,
    },
  };
}

function makeCallbackUpdate(data: string, chatId = 123) {
  return {
    update_id: Math.floor(Math.random() * 100000),
    callback_query: {
      id: String(Math.floor(Math.random() * 100000)),
      from: { id: chatId, is_bot: false, first_name: 'TestUser' },
      message: {
        message_id: 1,
        from: { id: 999, is_bot: true, first_name: 'Bot' },
        chat: { id: chatId, type: 'private' as const },
        date: Math.floor(Date.now() / 1000),
        text: 'Menu',
      },
      data,
      chat_instance: '1',
    },
  };
}

/**
 * Patch callApi on the Telegram instance's prototype chain so handleUpdate
 * never makes real HTTP requests. Returns a restore function.
 */
function patchCallApi(telegram: any, captured: Array<{ method: string; body: any }>): () => void {
  // Walk prototype chain to find where callApi is defined
  let proto = Object.getPrototypeOf(telegram);
  let originalCallApi: Function | null = null;
  let targetProto: any = null;

  while (proto) {
    const desc = Object.getOwnPropertyDescriptor(proto, 'callApi');
    if (desc) {
      originalCallApi = desc.value;
      targetProto = proto;
      break;
    }
    proto = Object.getPrototypeOf(proto);
  }

  if (!targetProto || !originalCallApi) {
    throw new Error('callApi not found in prototype chain');
  }

  // Replace on the prototype (affects all instances, so restore after tests)
  targetProto.callApi = async function (method: string, data: any) {
    captured.push({ method, body: data });
    if (method === 'sendMessage') return { message_id: 1 };
    if (method === 'answerCallbackQuery') return true;
    if (method === 'setMyCommands') return true;
    return {};
  };

  return () => {
    targetProto.callApi = originalCallApi;
  };
}

// ── Tests ───────────────────────────────────────────────────────────

describe('telegram integration', () => {
  const origToken = config.TELEGRAM_BOT_TOKEN;
  let sandbox: sinon.SinonSandbox;

  beforeEach(() => {
    sandbox = sinon.createSandbox();
    sessions.clearSession('123', 'telegram');
  });

  afterEach(() => {
    sandbox.restore();
    config.TELEGRAM_BOT_TOKEN = origToken;
  });

  // ── Bot creation ────────────────────────────────────────────────

  describe('createTelegramBot', () => {
    it('returns null when TELEGRAM_BOT_TOKEN is empty', () => {
      config.TELEGRAM_BOT_TOKEN = '';
      expect(createTelegramBot()).to.be.null;
    });

    it('returns a Telegraf instance when token is set', () => {
      config.TELEGRAM_BOT_TOKEN = '123456:ABC-DEF-test';
      const bot = createTelegramBot();
      expect(bot).to.not.be.null;
      expect(bot!.telegram).to.exist;
    });
  });

  // ── Command handling (full flow via handleUpdate) ───────────────

  describe('command handling', () => {
    let bot: any;
    let captured: Array<{ method: string; body: any }>;
    let restoreCallApi: () => void;

    before(() => {
      captured = [];
      config.TELEGRAM_BOT_TOKEN = '123456:test-commands';
      bot = createTelegramBot()!;
      bot.botInfo = FAKE_BOT_INFO;
      restoreCallApi = patchCallApi(bot.telegram, captured);
    });

    afterEach(() => {
      captured.length = 0;
    });

    after(() => {
      restoreCallApi();
      config.TELEGRAM_BOT_TOKEN = origToken;
    });

    function getSent(): any[] {
      return captured.filter(c => c.method === 'sendMessage').map(c => c.body);
    }

    it('responds to /help with command list', async () => {
      await bot.handleUpdate(makeCommandUpdate('/help'));
      const msgs = getSent();
      expect(msgs.length).to.be.greaterThan(0);
      expect(msgs[0].text).to.include('/menu');
      expect(msgs[0].text).to.include('/dashboard');
      expect(msgs[0].text).to.include('/draft');
    });

    it('responds to /menu with inline keyboard buttons', async () => {
      await bot.handleUpdate(makeCommandUpdate('/menu'));
      const msgs = getSent();
      expect(msgs[0].text).to.include('Control Center');
      expect(msgs[0].reply_markup).to.exist;
      expect(msgs[0].reply_markup.inline_keyboard).to.be.an('array');
      expect(msgs[0].reply_markup.inline_keyboard.length).to.equal(3);
    });

    it('sends Markdown parse_mode', async () => {
      await bot.handleUpdate(makeCommandUpdate('/help'));
      const msgs = getSent();
      expect(msgs[0].parse_mode).to.equal('Markdown');
    });

    it('responds to /dashboard with war-room data', async () => {
      sandbox.stub(api, 'getRooms').resolves({
        rooms: [{ room_id: 'r1', status: 'passed', message_count: 5 }],
        summary: { total: 1, passed: 1 },
      });
      await bot.handleUpdate(makeCommandUpdate('/dashboard'));
      const msgs = getSent();
      expect(msgs[0].text).to.include('COMMAND CENTER');
      expect(msgs[0].text).to.include('ONLINE');
    });

    it('responds to /status with room list', async () => {
      sandbox.stub(api, 'getRooms').resolves({
        rooms: [
          { room_id: 'room-1', status: 'passed', message_count: 10 },
          { room_id: 'room-2', status: 'engineering', message_count: 3 },
        ],
        summary: { total: 2, passed: 1, engineering: 1 },
      });
      await bot.handleUpdate(makeCommandUpdate('/status'));
      const msgs = getSent();
      expect(msgs[0].text).to.include('room-1');
      expect(msgs[0].text).to.include('PASSED');
    });

    it('responds to /plans with plan list', async () => {
      sandbox.stub(api, 'getPlans').resolves({
        plans: [{ plan_id: 'p1', title: 'Auth System', status: 'launched' }],
        count: 1,
      });
      await bot.handleUpdate(makeCommandUpdate('/plans'));
      const msgs = getSent();
      expect(msgs[0].text).to.include('Auth System');
    });

    it('responds to /draft without args with idea prompt', async () => {
      await bot.handleUpdate(makeCommandUpdate('/draft'));
      const msgs = getSent();
      expect(msgs[0].text).to.include('idea');
      expect(sessions.getSession('123', 'telegram').mode).to.equal('awaiting_idea');
    });

    it('responds to /cancel by clearing session', async () => {
      sessions.setMode('123', 'telegram', 'editing');
      sessions.setPlan('123', 'telegram', 'p1');
      await bot.handleUpdate(makeCommandUpdate('/cancel'));
      const msgs = getSent();
      expect(msgs[0].text).to.include('cancelled');
      expect(sessions.getSession('123', 'telegram').mode).to.equal('idle');
    });

    it('responds to /skills with skill list', async () => {
      sandbox.stub(api, 'getSkills').resolves([{ name: 'code-review', tags: ['qa'] }]);
      await bot.handleUpdate(makeCommandUpdate('/skills'));
      const msgs = getSent();
      expect(msgs[0].text).to.include('code-review');
    });

    it('responds to /usage with stats', async () => {
      sandbox.stub(api, 'getStats').resolves({
        total_plans: { value: 3 },
        active_epics: { value: 5 },
        completion_rate: { value: 75.0 },
        escalations_pending: { value: 0 },
      });
      await bot.handleUpdate(makeCommandUpdate('/usage'));
      const msgs = getSent();
      expect(msgs[0].text).to.include('STATS REPORT');
      expect(msgs[0].text).to.include('75.0%');
    });
  });

  // ── Callback queries ────────────────────────────────────────────

  describe('callback queries', () => {
    let bot: any;
    let captured: Array<{ method: string; body: any }>;
    let restoreCallApi: () => void;

    before(() => {
      captured = [];
      config.TELEGRAM_BOT_TOKEN = '123456:test-cbs';
      bot = createTelegramBot()!;
      bot.botInfo = FAKE_BOT_INFO;
      restoreCallApi = patchCallApi(bot.telegram, captured);
    });

    afterEach(() => { captured.length = 0; });
    after(() => { restoreCallApi(); config.TELEGRAM_BOT_TOKEN = origToken; });

    it('handles menu:main callback and returns main menu', async () => {
      await bot.handleUpdate(makeCallbackUpdate('menu:main'));
      const msgs = captured.filter(c => c.method === 'sendMessage');
      expect(msgs.length).to.be.greaterThan(0);
      expect(msgs[0].body.text).to.include('Control Center');
    });

    it('handles menu:cat:monitoring callback', async () => {
      await bot.handleUpdate(makeCallbackUpdate('menu:cat:monitoring'));
      const msgs = captured.filter(c => c.method === 'sendMessage');
      expect(msgs[0].body.text).to.include('Monitoring');
    });

    it('answers callback query to dismiss loading spinner', async () => {
      await bot.handleUpdate(makeCallbackUpdate('menu:main'));
      const answers = captured.filter(c => c.method === 'answerCallbackQuery');
      expect(answers.length).to.be.greaterThan(0);
    });

    it('handles cmd:dashboard callback with API data', async () => {
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });
      await bot.handleUpdate(makeCallbackUpdate('cmd:dashboard'));
      const msgs = captured.filter(c => c.method === 'sendMessage');
      expect(msgs[0].body.text).to.include('COMMAND CENTER');
    });
  });

  // ── Free text (stateful editing) ────────────────────────────────

  describe('free text handling', () => {
    let bot: any;
    let captured: Array<{ method: string; body: any }>;
    let restoreCallApi: () => void;

    before(() => {
      captured = [];
      config.TELEGRAM_BOT_TOKEN = '123456:test-text';
      bot = createTelegramBot()!;
      bot.botInfo = FAKE_BOT_INFO;
      restoreCallApi = patchCallApi(bot.telegram, captured);
    });

    afterEach(() => { captured.length = 0; sessions.clearSession('123', 'telegram'); });
    after(() => { restoreCallApi(); config.TELEGRAM_BOT_TOKEN = origToken; });

    it('ignores text when session is idle', async () => {
      await bot.handleUpdate(makeTextUpdate('hello world'));
      const msgs = captured.filter(c => c.method === 'sendMessage');
      expect(msgs).to.have.lengthOf(0);
    });

    it('processes text when in awaiting_idea mode', async () => {
      sessions.setMode('123', 'telegram', 'awaiting_idea');
      sessions.setPlan('123', 'telegram', 'new');
      sandbox.stub(api, 'refinePlan').resolves({ plan: '# My Plan', explanation: 'Created' });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'test-1234' });

      await bot.handleUpdate(makeTextUpdate('Build a todo app'));
      const msgs = captured.filter(c => c.method === 'sendMessage');
      expect(msgs.length).to.be.greaterThan(0);
      expect(msgs[0].body.text).to.include('Drafting');
    });

    it('processes text when in editing mode', async () => {
      sessions.setMode('123', 'telegram', 'editing');
      sessions.setPlan('123', 'telegram', 'p1');
      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Updated', explanation: 'Refined' });
      sandbox.stub(api, 'savePlan').resolves({ status: 'saved' });

      await bot.handleUpdate(makeTextUpdate('Add more epics'));
      const msgs = captured.filter(c => c.method === 'sendMessage');
      expect(msgs.length).to.be.greaterThan(0);
      expect(msgs[0].body.text).to.include('Refining');
    });
  });
});
