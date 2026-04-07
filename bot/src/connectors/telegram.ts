import https from 'https';
import { Telegraf, Markup, Context } from 'telegraf';
import { Platform, Connector, ConnectorConfig, ConnectorStatus, HealthCheckResult, SetupStep, ValidationResult } from './base';
import { routeCommand, routeCallback, handleStatefulText, BotResponse } from '../commands';
import { getSession } from '../sessions';

// Force IPv4 — IPv6 to Telegram's servers is unreachable on many networks,
// and Node 20's Happy Eyeballs fallback can stall instead of recovering.
const ipv4Agent = new https.Agent({ keepAlive: true, keepAliveMsecs: 10000, family: 4 });

export class TelegramConnector implements Connector {
  public readonly platform: Platform = 'telegram';
  public status: ConnectorStatus = 'disconnected';
  public bot: Telegraf | null = null;
  private authorizedChats: Set<string> = new Set();
  private pairingCode: string = '';

  public async start(config: ConnectorConfig): Promise<void> {
    const token = config.credentials.token;
    if (!token) {
      this.status = 'error';
      throw new Error('Telegram bot token is missing in credentials');
    }

    this.status = 'connecting';
    this.pairingCode = config.pairing_code || Math.random().toString(16).slice(2, 10);
    this.authorizedChats = new Set(config.authorized_users || []);

    this.bot = new Telegraf(token, { telegram: { agent: ipv4Agent } });

    // ── Authorization middleware ──────────────────────────────────
    this.bot.use(async (ctx, next) => {
      const chatId = String(ctx.chat?.id);
      if (!chatId) return;

      // Always allow /pair
      if ((ctx.message as any)?.text?.startsWith('/pair')) return next();

      // Check authorization (allow if no chats configured yet = first user)
      if (this.authorizedChats.size > 0 && !this.authorizedChats.has(chatId)) {
        await ctx.reply(
          `🔒 *Unauthorized.* This bot is private. Use \`/pair ${this.pairingCode}\` to authorize.`,
          { parse_mode: 'Markdown' }
        );
        return;
      }

      return next();
    });

    // ── /pair command ─────────────────────────────────────────────
    this.bot.command('pair', async (ctx) => {
      const chatId = String(ctx.chat.id);
      const args = ctx.message.text.split(/\s+/).slice(1).join(' ');
      if (args === this.pairingCode) {
        this.authorizedChats.add(chatId);
        // Note: In a real app, we should probably persist this back to config
        await ctx.reply('✅ *Pairing successful!* You are now authorized.', { parse_mode: 'Markdown' });
      } else {
        await ctx.reply('❌ *Invalid pairing code.*', { parse_mode: 'Markdown' });
      }
    });

    // ── Slash commands ────────────────────────────────────────────
    const COMMANDS = [
      'menu', 'dashboard', 'status', 'compact', 'plans', 'errors',
      'skills', 'usage', 'help', 'start', 'cancel', 'edit',
      'feedback', 'preferences', 'subscriptions', 'progress',
    ] as const;

    for (const cmd of COMMANDS) {
      this.bot.command(cmd, async (ctx) => {
        const userId = String(ctx.chat.id);
        const responses = await routeCommand(userId, 'telegram', cmd);
        await this.sendResponses(ctx, responses);
      });
    }

    // Commands with inline arguments
    for (const cmd of ['draft', 'setdir', 'feedback'] as const) {
      this.bot.command(cmd, async (ctx) => {
        const userId = String(ctx.chat.id);
        const args = ctx.message.text.replace(new RegExp(`^\\/${cmd}(@\\S+)?`), '').trim();
        const responses = await routeCommand(userId, 'telegram', cmd, args);
        await this.sendResponses(ctx, responses);
      });
    }

    // ── Callback queries (inline keyboard buttons) ────────────────
    this.bot.on('callback_query', async (ctx) => {
      const cbQuery = ctx.callbackQuery;
      const userId = String((cbQuery as any).message?.chat?.id);
      const data = (cbQuery as any).data as string | undefined;
      if (!userId || !data) return;

      await ctx.answerCbQuery(); // stop loading spinner

      const responses = await routeCallback(userId, 'telegram', data);
      await this.sendResponsesChat(userId, responses);
    });

    // ── Free text (stateful AI editing) ───────────────────────────
    this.bot.on('text', async (ctx) => {
      const userId = String(ctx.chat.id);
      const msgText = ctx.message.text.trim();

      // Skip if it's a command
      if (msgText.startsWith('/')) return;

      const session = getSession(userId, 'telegram');
      if (['drafting', 'editing', 'awaiting_idea'].includes(session.mode)) {
        const responses = await handleStatefulText(userId, 'telegram', msgText);
        await this.sendResponses(ctx, responses);
      }
    });

    // ── EPIC-005: File/Document handling ──────────────────────────
    const handleTelegramFiles = async (ctx: Context) => {
      const userId = String(ctx.chat.id);
      const msg = ctx.message as any;
      const session = getSession(userId, 'telegram');
      
      // We only care about files if they are in drafting/editing mode
      if (!session.activePlanId || session.activePlanId === 'new') return;

      const files: any[] = [];
      
      if (msg.document) {
        files.push(msg.document);
      } else if (msg.photo) {
        // Take the largest photo
        files.push(msg.photo[msg.photo.length - 1]);
      } else if (msg.audio) {
        files.push(msg.audio);
      } else if (msg.voice) {
        files.push(msg.voice);
      }

      if (!files.length) return;

      const downloadable: any[] = [];
      for (const f of files) {
        const fileId = f.file_id;
        const link = await ctx.telegram.getFileLink(fileId);
        const fileName = f.file_name || `file_${fileId.slice(-8)}`;
        const mimeType = f.mime_type || 'application/octet-stream';
        
        try {
          const res = await fetch(link.href);
          if (!res.ok) continue;
          const buffer = await res.arrayBuffer();
          downloadable.push({
            name: fileName,
            contentType: mimeType,
            data: new Uint8Array(buffer),
          });
        } catch (err) {
          console.warn(`[TELEGRAM] Failed to download ${fileName}:`, err);
        }
      }

      if (downloadable.length > 0) {
        const { handleFileAttachments } = await import('../commands');
        const responses = await handleFileAttachments(userId, 'telegram', downloadable);
        await this.sendResponses(ctx, responses);
      }
    };

    this.bot.on('document', handleTelegramFiles);
    this.bot.on('photo', handleTelegramFiles);
    this.bot.on('audio', handleTelegramFiles);
    this.bot.on('voice', handleTelegramFiles);

    // ── Register command menu with Telegram ───────────────────────
    await this.bot.telegram.setMyCommands([
      { command: 'menu', description: '🏢 Main Control Center' },
      { command: 'dashboard', description: '📊 Real-time War-Room progress' },
      { command: 'setdir', description: '📂 Set target project directory' },
      { command: 'draft', description: '📝 Draft a new Plan with AI' },
      { command: 'status', description: '💻 List running War-Rooms' },
      { command: 'help', description: '❓ Detailed user guide' },
    ]).catch(err => console.warn('[TELEGRAM] Failed to register commands:', err.message));

    // bot.launch() never resolves — it runs the polling loop forever.
    // Fire-and-forget so the connector start() can complete.
    this.bot.launch({ dropPendingUpdates: true })
      .catch(err => console.error('[TELEGRAM] Polling error:', err.message));
    this.status = 'connected';
    console.log(`[TELEGRAM] Connector started. (pairing code: ${this.pairingCode})`);
  }

  public async stop(): Promise<void> {
    if (this.bot) {
      await this.bot.stop();
      this.bot = null;
    }
    this.status = 'disconnected';
  }

  public async healthCheck(): Promise<HealthCheckResult> {
    if (this.status !== 'connected' || !this.bot) {
      return { status: 'unhealthy', message: `Bot is ${this.status}` };
    }
    try {
      await this.bot.telegram.getMe();
      return { status: 'healthy' };
    } catch (error: any) {
      return { status: 'unhealthy', message: error.message };
    }
  }

  public async sendMessage(targetId: string, response: BotResponse): Promise<void> {
    if (!this.bot) throw new Error('Telegram bot not started');
    await this.sendResponsesChat(targetId, [response]);
  }

  public getSetupInstructions(): SetupStep[] {
    return [
      {
        title: 'Create a Bot',
        description: 'Talk to @BotFather on Telegram to create a new bot.',
        instructions: '1. Send /newbot to @BotFather\n2. Follow the prompts to name your bot\n3. Copy the API Token provided.',
      },
      {
        title: 'Configure Token',
        description: 'Add your bot token to the configuration.',
        instructions: 'Paste the token into the "token" field in credentials.',
      }
    ];
  }

  public validateConfig(config: ConnectorConfig): ValidationResult {
    const errors: string[] = [];
    if (!config.credentials.token) {
      errors.push('Missing Telegram bot token');
    }
    return {
      valid: errors.length === 0,
      errors: errors.length > 0 ? errors : undefined,
    };
  }

  private static buildKeyboard(buttons: BotResponse['buttons']) {
    return buttons!.map(row =>
      row.map(btn =>
        btn.url ? Markup.button.url(btn.label, btn.url) : Markup.button.callback(btn.label, btn.callbackData)
      )
    );
  }

  private async sendResponses(ctx: Context, responses: BotResponse[]): Promise<void> {
    for (const resp of responses) {
      if (resp.buttons && resp.buttons.length) {
        const keyboard = TelegramConnector.buildKeyboard(resp.buttons);
        await ctx.reply(resp.text, {
          parse_mode: 'Markdown',
          ...Markup.inlineKeyboard(keyboard),
        });
      } else {
        await ctx.reply(resp.text, { parse_mode: 'Markdown' });
      }
    }
  }

  private async sendResponsesChat(chatId: string, responses: BotResponse[]): Promise<void> {
    if (!this.bot) return;
    for (const resp of responses) {
      if (resp.buttons && resp.buttons.length) {
        const keyboard = TelegramConnector.buildKeyboard(resp.buttons);
        await this.bot.telegram.sendMessage(chatId, resp.text, {
          parse_mode: 'Markdown',
          ...Markup.inlineKeyboard(keyboard),
        });
      } else {
        await this.bot.telegram.sendMessage(chatId, resp.text, { parse_mode: 'Markdown' });
      }
    }
  }
}
