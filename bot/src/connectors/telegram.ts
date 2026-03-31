import { Telegraf, Markup, Context } from 'telegraf';
import { Platform, Connector, ConnectorConfig, ConnectorStatus, HealthCheckResult, SetupStep, ValidationResult } from './base';
import { routeCommand, routeCallback, handleStatefulText, BotResponse } from '../commands';
import { getSession } from '../sessions';

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

    this.bot = new Telegraf(token);

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

    // /draft with optional inline argument
    this.bot.command('draft', async (ctx) => {
      const userId = String(ctx.chat.id);
      const args = ctx.message.text.replace(/^\/draft(@\S+)?/, '').trim();
      const responses = await routeCommand(userId, 'telegram', 'draft', args);
      await this.sendResponses(ctx, responses);
    });

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

    // ── Register command menu with Telegram ───────────────────────
    await this.bot.telegram.setMyCommands([
      { command: 'menu', description: '🏢 Main Control Center' },
      { command: 'dashboard', description: '📊 Real-time War-Room progress' },
      { command: 'draft', description: '📝 Draft a new Plan with AI' },
      { command: 'status', description: '💻 List running War-Rooms' },
      { command: 'help', description: '❓ Detailed user guide' },
    ]).catch(err => console.warn('[TELEGRAM] Failed to register commands:', err.message));

    await this.bot.launch({ dropPendingUpdates: true });
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

  private async sendResponses(ctx: Context, responses: BotResponse[]): Promise<void> {
    for (const resp of responses) {
      if (resp.buttons && resp.buttons.length) {
        const keyboard = resp.buttons.map(row =>
          row.map(btn => Markup.button.callback(btn.label, btn.callbackData))
        );
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
        const keyboard = resp.buttons.map(row =>
          row.map(btn => Markup.button.callback(btn.label, btn.callbackData))
        );
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
