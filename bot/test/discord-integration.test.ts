/**
 * Discord bot integration tests.
 *
 * Tests the full flow: Discord event → handler → command router → API → response.
 * Uses Client.emit() to simulate real Discord events with mock interaction/message objects.
 */

import { expect } from 'chai';
import sinon from 'sinon';
import config from '../src/config';
import api from '../src/api';
import * as sessions from '../src/sessions';
import { createDiscordBot } from '../src/discord';

// ── Mock factories ──────────────────────────────────────────────────

function mockSlashInteraction(commandName: string, options: Record<string, any> = {}) {
  return {
    isButton: () => false,
    isChatInputCommand: () => true,
    commandName,
    user: { id: '456' },
    replied: false,
    deferred: false,
    options: {
      getString: sinon.stub().callsFake((name: string) => options[name] || null),
    },
    reply: sinon.stub().resolves(),
    followUp: sinon.stub().resolves(),
    deferReply: sinon.stub().resolves(),
    deferUpdate: sinon.stub().resolves(),
    channel: { send: sinon.stub().resolves() },
  };
}

function mockButtonInteraction(customId: string) {
  return {
    isButton: () => true,
    isChatInputCommand: () => false,
    user: { id: '456' },
    customId,
    deferUpdate: sinon.stub().resolves(),
    channel: { send: sinon.stub().resolves() },
  };
}

function mockMessage(content: string, overrides: any = {}) {
  return {
    id: 'msg-' + Math.random().toString(16).slice(2, 8),
    author: { id: overrides.authorId || '456', username: 'TestUser', bot: false },
    guild: { id: 'guild-1' },
    channel: {
      id: 'ch-1',
      name: 'general',
      send: sinon.stub().resolves(),
      sendTyping: sinon.stub().resolves(),
    },
    content,
    createdAt: new Date(),
    mentions: { has: sinon.stub().returns(false) },
    reply: sinon.stub().resolves(),
    ...overrides,
  };
}

const WAIT = (ms = 100) => new Promise(r => setTimeout(r, ms));

// ── Tests ───────────────────────────────────────────────────────────

describe('discord integration', () => {
  const origToken = config.DISCORD_TOKEN;
  let sandbox: sinon.SinonSandbox;

  beforeEach(() => {
    sandbox = sinon.createSandbox();
    sessions.clearSession('456', 'discord');
  });

  afterEach(() => {
    sandbox.restore();
    config.DISCORD_TOKEN = origToken;
  });

  // ── Bot creation ────────────────────────────────────────────────

  describe('createDiscordBot', () => {
    it('returns null when DISCORD_TOKEN is empty', () => {
      config.DISCORD_TOKEN = '';
      expect(createDiscordBot()).to.be.null;
    });

    it('returns a Client instance when token is set', () => {
      config.DISCORD_TOKEN = 'fake-discord-token';
      const client = createDiscordBot();
      expect(client).to.not.be.null;
      expect(client!.on).to.be.a('function');
    });
  });

  // ── Slash commands ──────────────────────────────────────────────

  describe('slash command handling', () => {
    let client: any;

    before(() => {
      config.DISCORD_TOKEN = 'fake-discord-slash';
      client = createDiscordBot();
    });

    after(() => {
      config.DISCORD_TOKEN = origToken;
    });

    it('responds to /menu with buttons', async () => {
      const interaction = mockSlashInteraction('menu');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.reply.calledOnce).to.be.true;
      const payload = interaction.reply.firstCall.args[0];
      expect(payload.content).to.include('Control Center');
      expect(payload.components).to.be.an('array');
      expect(payload.components.length).to.be.greaterThan(0);
    });

    it('responds to /help with command list', async () => {
      const interaction = mockSlashInteraction('help');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.reply.calledOnce).to.be.true;
      const content = interaction.reply.firstCall.args[0].content;
      expect(content).to.include('/menu');
      expect(content).to.include('/dashboard');
    });

    it('responds to /dashboard with war-room data', async () => {
      sandbox.stub(api, 'getRooms').resolves({
        rooms: [{ room_id: 'r1', status: 'passed', message_count: 5 }],
        summary: { total: 1, passed: 1 },
      });

      const interaction = mockSlashInteraction('dashboard');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.reply.calledOnce).to.be.true;
      expect(interaction.reply.firstCall.args[0].content).to.include('COMMAND CENTER');
    });

    it('defers reply for long-running commands (draft)', async () => {
      const interaction = mockSlashInteraction('draft');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.deferReply.calledOnce).to.be.true;
    });

    it('defers reply for long-running commands (edit)', async () => {
      sandbox.stub(api, 'getPlans').resolves({ plans: [], count: 0 });

      const interaction = mockSlashInteraction('edit');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.deferReply.calledOnce).to.be.true;
    });

    it('does NOT defer for non-long-running commands (menu)', async () => {
      const interaction = mockSlashInteraction('menu');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.deferReply.called).to.be.false;
    });

    it('passes draft idea option to command router', async () => {
      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Test', explanation: 'Created' });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'test-1234' });

      const interaction = mockSlashInteraction('draft', { idea: 'Build auth system' });
      client.emit('interactionCreate', interaction);
      await WAIT(200);

      expect(interaction.deferReply.calledOnce).to.be.true;
      expect(interaction.followUp.called).to.be.true;
      // Multiple followUp calls: first is "Drafting...", then "Plan Drafted"
      const allContent = interaction.followUp.getCalls().map((c: any) => c.args[0].content).join(' ');
      expect(allContent).to.include('Plan Drafted');
    });

    it('responds to /cancel by clearing session', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      const interaction = mockSlashInteraction('cancel');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.reply.calledOnce).to.be.true;
      expect(interaction.reply.firstCall.args[0].content).to.include('cancelled');
      expect(sessions.getSession('456', 'discord').mode).to.equal('idle');
    });

    it('responds to /plans with plan list', async () => {
      sandbox.stub(api, 'getPlans').resolves({
        plans: [{ plan_id: 'p1', title: 'Auth System', status: 'launched' }],
        count: 1,
      });

      const interaction = mockSlashInteraction('plans');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.reply.calledOnce).to.be.true;
      expect(interaction.reply.firstCall.args[0].content).to.include('Auth System');
    });

    it('converts Telegram *bold* to Discord **bold**', async () => {
      const interaction = mockSlashInteraction('help');
      client.emit('interactionCreate', interaction);
      await WAIT();

      const content = interaction.reply.firstCall.args[0].content;
      // Original uses *bold* (Telegram style) — Discord adapter converts to **bold**
      expect(content).to.include('**');
    });
  });

  // ── Button interactions ─────────────────────────────────────────

  describe('button interaction handling', () => {
    let client: any;

    before(() => {
      config.DISCORD_TOKEN = 'fake-discord-buttons';
      client = createDiscordBot();
    });

    after(() => {
      config.DISCORD_TOKEN = origToken;
    });

    it('handles menu:main button and sends to channel', async () => {
      const interaction = mockButtonInteraction('menu:main');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.deferUpdate.calledOnce).to.be.true;
      expect(interaction.channel.send.calledOnce).to.be.true;
      expect(interaction.channel.send.firstCall.args[0].content).to.include('Control Center');
    });

    it('handles menu:cat:plans button', async () => {
      const interaction = mockButtonInteraction('menu:cat:plans');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.channel.send.calledOnce).to.be.true;
      expect(interaction.channel.send.firstCall.args[0].content).to.include('Plans');
    });

    it('handles cmd:dashboard button with API data', async () => {
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      const interaction = mockButtonInteraction('cmd:dashboard');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.channel.send.calledOnce).to.be.true;
      expect(interaction.channel.send.firstCall.args[0].content).to.include('COMMAND CENTER');
    });

    it('does not send for unknown callback (empty response)', async () => {
      const interaction = mockButtonInteraction('unknown:callback');
      client.emit('interactionCreate', interaction);
      await WAIT();

      expect(interaction.deferUpdate.calledOnce).to.be.true;
      expect(interaction.channel.send.called).to.be.false;
    });
  });

  // ── Message handling ────────────────────────────────────────────

  describe('message handling', () => {
    let client: any;

    before(() => {
      config.DISCORD_TOKEN = 'fake-discord-messages';
      client = createDiscordBot();
    });

    after(() => {
      config.DISCORD_TOKEN = origToken;
    });

    it('ignores bot messages', async () => {
      const msg = mockMessage('hello');
      msg.author.bot = true;

      client.emit('messageCreate', msg);
      await WAIT();

      expect(msg.channel.send.called).to.be.false;
      expect(msg.reply.called).to.be.false;
    });

    it('ignores DM messages (no guild)', async () => {
      const msg = mockMessage('hello');
      msg.guild = null;

      client.emit('messageCreate', msg);
      await WAIT();

      expect(msg.channel.send.called).to.be.false;
    });

    it('ignores text when session is idle', async () => {
      const msg = mockMessage('just chatting');
      client.emit('messageCreate', msg);
      await WAIT();

      expect(msg.channel.send.called).to.be.false;
    });

    it('processes text when in editing mode', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Updated', explanation: 'Refined' });
      sandbox.stub(api, 'savePlan').resolves({ status: 'saved' });

      const msg = mockMessage('Add auth epic');
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect(msg.channel.send.called).to.be.true;
      const content = msg.channel.send.firstCall.args[0].content;
      expect(content).to.include('Refining');
    });

    it('processes text when in awaiting_idea mode', async () => {
      sessions.setMode('456', 'discord', 'awaiting_idea');
      sessions.setPlan('456', 'discord', 'new');

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# My Plan', explanation: 'Created' });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'test-plan' });

      const msg = mockMessage('Build a todo app');
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect(msg.channel.send.called).to.be.true;
      const content = msg.channel.send.firstCall.args[0].content;
      expect(content).to.include('Drafting');
    });
  });

  // ── Cross-platform isolation ────────────────────────────────────

  describe('platform isolation', () => {
    it('discord and telegram sessions are independent', () => {
      sessions.setMode('456', 'telegram', 'editing');
      sessions.setMode('456', 'discord', 'drafting');

      expect(sessions.getSession('456', 'telegram').mode).to.equal('editing');
      expect(sessions.getSession('456', 'discord').mode).to.equal('drafting');

      sessions.clearSession('456', 'discord');

      expect(sessions.getSession('456', 'telegram').mode).to.equal('editing');
      expect(sessions.getSession('456', 'discord').mode).to.equal('idle');
    });

    it('same command produces same content on both platforms', async () => {
      const { routeCommand } = await import('../src/commands.ts');
      sandbox.stub(api, 'getRooms').resolves({ rooms: [], summary: {} });

      const [telegramResp] = await routeCommand('u1', 'telegram', 'dashboard');
      const [discordResp] = await routeCommand('u1', 'discord', 'dashboard');

      expect(telegramResp.text).to.equal(discordResp.text);
    });
  });
});
