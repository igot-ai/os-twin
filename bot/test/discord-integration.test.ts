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
    sandbox.stub(api, 'getPlanAssets').resolves({ assets: [], count: 0 });
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

    it('saves attachments to the active plan while editing', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      sandbox.stub(globalThis, 'fetch').resolves({
        ok: true,
        arrayBuffer: async () => new Uint8Array([1, 2, 3]).buffer,
        headers: new Headers({ 'content-type': 'image/png' }),
      } as any);
      sandbox.stub(api, 'uploadPlanAssets').resolves({
        assets: [
          {
            filename: 'stored-mockup.png',
            original_name: 'mockup.png',
            mime_type: 'image/png',
            uploaded_at: '2026-04-05T00:00:00Z',
          },
        ],
      });

      const msg = mockMessage('', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/mockup.png', name: 'mockup.png', contentType: 'image/png' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect((api.uploadPlanAssets as sinon.SinonStub).calledOnce).to.be.true;
      expect(msg.channel.send.called).to.be.true;
      expect(msg.channel.send.firstCall.args[0].content).to.include('Saved `mockup.png`');
      expect(msg.channel.send.firstCall.args[0].content).to.include('mockup.png');
    });

    it('sends correct plan_id to upload API — plan isolation', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'my-special-plan');

      sandbox.stub(globalThis, 'fetch').resolves({
        ok: true,
        arrayBuffer: async () => new Uint8Array([9]).buffer,
        headers: new Headers({ 'content-type': 'image/jpeg' }),
      } as any);
      const uploadStub = sandbox.stub(api, 'uploadPlanAssets').resolves({
        assets: [{ filename: 's.jpg', original_name: 'photo.jpg', mime_type: 'image/jpeg', uploaded_at: '2026-04-05T00:00:00Z' }],
      });

      const msg = mockMessage('', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/photo.jpg', name: 'photo.jpg', contentType: 'image/jpeg' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect(uploadStub.firstCall.args[0]).to.equal('my-special-plan');
    });

    it('defers attachments in awaiting_idea until plan is created by draft', async () => {
      sessions.setMode('456', 'discord', 'awaiting_idea');
      sessions.setPlan('456', 'discord', 'new');

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# New Plan', explanation: 'Created' });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'deferred-plan' });
      sandbox.stub(globalThis, 'fetch').resolves({
        ok: true,
        arrayBuffer: async () => new Uint8Array([1]).buffer,
        headers: new Headers({ 'content-type': 'image/png' }),
      } as any);
      sandbox.stub(api, 'uploadPlanAssets').resolves({
        assets: [{ filename: 's.png', original_name: 'img.png', mime_type: 'image/png', uploaded_at: '2026-04-05T00:00:00Z' }],
      });

      // User sends idea text + image together
      const msg = mockMessage('Build a landing page', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/img.png', name: 'img.png', contentType: 'image/png' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(400);

      // Plan was created, then attachment saved to it
      expect((api.uploadPlanAssets as sinon.SinonStub).calledOnce).to.be.true;
      expect((api.uploadPlanAssets as sinon.SinonStub).firstCall.args[0]).to.equal('deferred-plan');
      const allContent = msg.channel.send.getCalls().map((c: any) => c.args[0].content).join(' ');
      expect(allContent).to.include('Plan Drafted');
      expect(allContent).to.include('Saved `img.png`');
    });

    it('ignores attachments when session is idle', async () => {
      // Session is idle by default
      const msg = mockMessage('', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/img.png', name: 'img.png', contentType: 'image/png' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect(msg.channel.send.called).to.be.false;
    });

    it('reports failure when attachment has no URL', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      const msg = mockMessage('', {
        attachments: new Map([
          ['a1', { name: 'broken.png', contentType: 'image/png' /* no url */ }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect(msg.channel.send.called).to.be.true;
      const content = msg.channel.send.firstCall.args[0].content;
      expect(content).to.include('could not be saved');
      expect(content).to.include('missing download URL');
    });

    it('reports failure when Discord CDN returns non-200', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      sandbox.stub(globalThis, 'fetch').resolves({
        ok: false,
        status: 403,
        headers: new Headers(),
      } as any);

      const msg = mockMessage('', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/expired.png', name: 'expired.png', contentType: 'image/png' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect(msg.channel.send.called).to.be.true;
      const content = msg.channel.send.firstCall.args[0].content;
      expect(content).to.include('could not be saved');
      expect(content).to.include('download failed');
    });

    it('reports failure when network error during download', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      sandbox.stub(globalThis, 'fetch').rejects(new Error('ECONNRESET'));

      const msg = mockMessage('', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/unreachable.png', name: 'unreachable.png', contentType: 'image/png' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect(msg.channel.send.called).to.be.true;
      const content = msg.channel.send.firstCall.args[0].content;
      expect(content).to.include('could not be saved');
      expect(content).to.include('ECONNRESET');
    });

    it('reports failure when upload API returns error', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      sandbox.stub(globalThis, 'fetch').resolves({
        ok: true,
        arrayBuffer: async () => new Uint8Array([1, 2]).buffer,
        headers: new Headers({ 'content-type': 'image/png' }),
      } as any);
      sandbox.stub(api, 'uploadPlanAssets').resolves({
        error: 'Disk full',
        assets: [],
      });

      const msg = mockMessage('', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/img.png', name: 'img.png', contentType: 'image/png' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect(msg.channel.send.called).to.be.true;
      const content = msg.channel.send.firstCall.args[0].content;
      expect(content).to.include('could not be saved');
      expect(content).to.include('Disk full');
    });

    it('handles multiple attachments — all succeed', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      sandbox.stub(globalThis, 'fetch').resolves({
        ok: true,
        arrayBuffer: async () => new Uint8Array([1]).buffer,
        headers: new Headers({ 'content-type': 'image/png' }),
      } as any);
      sandbox.stub(api, 'uploadPlanAssets').resolves({
        assets: [
          { filename: 's1.png', original_name: 'a.png', mime_type: 'image/png', uploaded_at: '2026-04-05T00:00:00Z' },
          { filename: 's2.jpg', original_name: 'b.jpg', mime_type: 'image/jpeg', uploaded_at: '2026-04-05T00:00:00Z' },
        ],
      });

      const msg = mockMessage('', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/a.png', name: 'a.png', contentType: 'image/png' }],
          ['a2', { url: 'https://cdn.discordapp.com/b.jpg', name: 'b.jpg', contentType: 'image/jpeg' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect(msg.channel.send.called).to.be.true;
      const content = msg.channel.send.firstCall.args[0].content;
      expect(content).to.include('Saved 2 asset');
    });

    it('handles mixed success/failure across attachments', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      // fetch will succeed for one and fail for another
      const fetchStub = sandbox.stub(globalThis, 'fetch');
      fetchStub.onFirstCall().resolves({
        ok: true,
        arrayBuffer: async () => new Uint8Array([1]).buffer,
        headers: new Headers({ 'content-type': 'image/png' }),
      } as any);
      fetchStub.onSecondCall().resolves({
        ok: false,
        status: 404,
        headers: new Headers(),
      } as any);

      sandbox.stub(api, 'uploadPlanAssets').resolves({
        assets: [
          { filename: 's1.png', original_name: 'good.png', mime_type: 'image/png', uploaded_at: '2026-04-05T00:00:00Z' },
        ],
      });

      const msg = mockMessage('', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/good.png', name: 'good.png', contentType: 'image/png' }],
          ['a2', { url: 'https://cdn.discordapp.com/missing.jpg', name: 'missing.jpg', contentType: 'image/jpeg' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(200);

      expect(msg.channel.send.called).to.be.true;
      // Should have two messages: one for saved, one for failures
      const allContent = msg.channel.send.getCalls().map((c: any) => c.args[0].content).join(' ');
      expect(allContent).to.include('Saved `good.png`');
      expect(allContent).to.include('could not be saved');
      expect(allContent).to.include('missing.jpg');
    });

    it('processes text AND attachments in the same message', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      sandbox.stub(globalThis, 'fetch').resolves({
        ok: true,
        arrayBuffer: async () => new Uint8Array([1]).buffer,
        headers: new Headers({ 'content-type': 'image/png' }),
      } as any);
      sandbox.stub(api, 'uploadPlanAssets').resolves({
        assets: [{ filename: 's.png', original_name: 'ref.png', mime_type: 'image/png', uploaded_at: '2026-04-05T00:00:00Z' }],
      });
      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Updated with image ref' });
      sandbox.stub(api, 'savePlan').resolves({});

      const msg = mockMessage('Use this mockup for the header', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/ref.png', name: 'ref.png', contentType: 'image/png' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(300);

      const allContent = msg.channel.send.getCalls().map((c: any) => c.args[0].content).join(' ');
      // Both asset saved confirmation and plan refine confirmation
      expect(allContent).to.include('Saved `ref.png`');
      expect(allContent).to.include('Refining');
    });

    it('saves attachments when @mentioning the bot while editing a plan', async () => {
      sessions.setMode('456', 'discord', 'editing');
      sessions.setPlan('456', 'discord', 'p1');

      sandbox.stub(globalThis, 'fetch').resolves({
        ok: true,
        arrayBuffer: async () => new Uint8Array([1, 2, 3]).buffer,
        headers: new Headers({ 'content-type': 'image/png' }),
      } as any);
      sandbox.stub(api, 'uploadPlanAssets').resolves({
        assets: [
          { filename: 'stored-blog-img.png', original_name: 'blog-img.png', mime_type: 'image/png', uploaded_at: '2026-04-05T00:00:00Z' },
        ],
      });

      const msg = mockMessage('@os-twin Also use these images as assets for the blog!', {
        mentions: { has: sinon.stub().returns(true) },
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/blog-img.png', name: 'blog-img.png', contentType: 'image/png' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(300);

      expect((api.uploadPlanAssets as sinon.SinonStub).calledOnce).to.be.true;
      const allContent = msg.channel.send.getCalls().map((c: any) => c.args[0].content).join(' ');
      expect(allContent).to.include('Saved `blog-img.png`');
      expect(allContent).to.include('blog-img.png');
    });

    it('saves attachments after draft creates the plan (awaiting_idea + image)', async () => {
      sessions.setMode('456', 'discord', 'awaiting_idea');
      sessions.setPlan('456', 'discord', 'new');

      sandbox.stub(api, 'refinePlan').resolves({ plan: '# Blog Plan', explanation: 'Created blog' });
      sandbox.stub(api, 'createPlan').resolves({ plan_id: 'blog-plan-1234' });

      // fetch is used by persistAttachments to download from Discord CDN
      sandbox.stub(globalThis, 'fetch').resolves({
        ok: true,
        arrayBuffer: async () => new Uint8Array([10, 20, 30]).buffer,
        headers: new Headers({ 'content-type': 'image/png' }),
      } as any);
      sandbox.stub(api, 'uploadPlanAssets').resolves({
        assets: [
          { filename: 'stored-hero.png', original_name: 'hero.png', mime_type: 'image/png', uploaded_at: '2026-04-05T00:00:00Z' },
        ],
      });

      const msg = mockMessage('Build a coffee blog', {
        attachments: new Map([
          ['a1', { url: 'https://cdn.discordapp.com/hero.png', name: 'hero.png', contentType: 'image/png' }],
        ]),
      });
      client.emit('messageCreate', msg);
      await WAIT(400);

      // Plan should have been created first
      expect((api.createPlan as sinon.SinonStub).calledOnce).to.be.true;
      // Then attachments saved to the newly created plan
      expect((api.uploadPlanAssets as sinon.SinonStub).calledOnce).to.be.true;
      expect((api.uploadPlanAssets as sinon.SinonStub).firstCall.args[0]).to.equal('blog-plan-1234');

      const allContent = msg.channel.send.getCalls().map((c: any) => c.args[0].content).join(' ');
      expect(allContent).to.include('Drafting');
      expect(allContent).to.include('Plan Drafted');
      expect(allContent).to.include('Saved `hero.png`');
      expect(allContent).to.include('hero.png');
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
