/**
 * telegram.ts — Telegram bot adapter using Telegraf.
 *
 * Handles: long-polling, inline keyboards, callback queries, authorization.
 * Delegates all command logic to commands.ts.
 */

import { Telegraf, Markup, Context } from 'telegraf';
import config from './config';
import { routeCommand, routeCallback, handleStatefulText, BotResponse } from './commands';
import { getSession } from './sessions';

/** Authorized chat IDs (loaded from env or paired at runtime) */
const authorizedChats = new Set<string>();
const PAIRING_CODE = process.env.TELEGRAM_PAIRING_CODE || Math.random().toString(16).slice(2, 10);

// ── Response renderer ─────────────────────────────────────────────

async function sendResponses(ctx: Context, responses: BotResponse[]): Promise<void> {
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

async function sendResponsesChat(bot: Telegraf, chatId: string, responses: BotResponse[]): Promise<void> {
  for (const resp of responses) {
    if (resp.buttons && resp.buttons.length) {
      const keyboard = resp.buttons.map(row =>
        row.map(btn => Markup.button.callback(btn.label, btn.callbackData))
      );
      await bot.telegram.sendMessage(chatId, resp.text, {
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard(keyboard),
      });
    } else {
      await bot.telegram.sendMessage(chatId, resp.text, { parse_mode: 'Markdown' });
    }
  }
}

// ── Bot setup ─────────────────────────────────────────────────────

export function createTelegramBot(): Telegraf | null {
  if (!config.TELEGRAM_BOT_TOKEN) {
    console.log('[TELEGRAM] No TELEGRAM_BOT_TOKEN set. Telegram bot disabled.');
    return null;
  }

  const bot = new Telegraf(config.TELEGRAM_BOT_TOKEN);

  // Add initial authorized chat from env
  const envChatId = process.env.TELEGRAM_CHAT_ID;
  if (envChatId) authorizedChats.add(String(envChatId));

  // ── Authorization middleware ──────────────────────────────────
  bot.use(async (ctx, next) => {
    const chatId = String(ctx.chat?.id);
    if (!chatId) return;

    // Always allow /pair
    if ((ctx.message as any)?.text?.startsWith('/pair')) return next();

    // Check authorization (allow if no chats configured yet = first user)
    if (authorizedChats.size > 0 && !authorizedChats.has(chatId)) {
      await ctx.reply(
        `🔒 *Unauthorized.* This bot is private. Use \`/pair ${PAIRING_CODE}\` to authorize.`,
        { parse_mode: 'Markdown' }
      );
      return;
    }

    return next();
  });

  // ── /pair command ─────────────────────────────────────────────
  bot.command('pair', async (ctx) => {
    const chatId = String(ctx.chat.id);
    const args = ctx.message.text.split(/\s+/).slice(1).join(' ');
    if (args === PAIRING_CODE) {
      authorizedChats.add(chatId);
      await ctx.reply('✅ *Pairing successful!* You are now authorized.', { parse_mode: 'Markdown' });
    } else {
      await ctx.reply('❌ *Invalid pairing code.*', { parse_mode: 'Markdown' });
    }
  });

  // ── Slash commands ────────────────────────────────────────────
  const COMMANDS = [
    'menu', 'dashboard', 'status', 'compact', 'plans', 'errors',
    'skills', 'usage', 'help', 'start', 'cancel', 'edit',
    'startplan', 'viewplan', 'transcribe',
  ] as const;

  for (const cmd of COMMANDS) {
    bot.command(cmd, async (ctx) => {
      const userId = String(ctx.chat.id);
      const responses = await routeCommand(userId, 'telegram', cmd);
      await sendResponses(ctx, responses);
    });
  }

  // /draft with optional inline argument
  bot.command('draft', async (ctx) => {
    const userId = String(ctx.chat.id);
    const args = ctx.message.text.replace(/^\/draft(@\S+)?/, '').trim();
    const responses = await routeCommand(userId, 'telegram', 'draft', args);
    await sendResponses(ctx, responses);
  });

  // ── Callback queries (inline keyboard buttons) ────────────────
  bot.on('callback_query', async (ctx) => {
    const cbQuery = ctx.callbackQuery;
    const userId = String((cbQuery as any).message?.chat?.id);
    const data = (cbQuery as any).data as string | undefined;
    if (!userId || !data) return;

    await ctx.answerCbQuery(); // stop loading spinner

    const responses = await routeCallback(userId, 'telegram', data);
    await sendResponsesChat(bot, userId, responses);
  });

  // ── Free text (stateful AI editing) ───────────────────────────
  bot.on('text', async (ctx) => {
    const userId = String(ctx.chat.id);
    const msgText = ctx.message.text.trim();

    // Skip if it's a command
    if (msgText.startsWith('/')) return;

    const session = getSession(userId, 'telegram');
    if (['drafting', 'editing', 'awaiting_idea'].includes(session.mode)) {
      const responses = await handleStatefulText(userId, 'telegram', msgText);
      await sendResponses(ctx, responses);
    }
  });

  // ── Register command menu with Telegram ───────────────────────
  bot.telegram.setMyCommands([
    { command: 'menu', description: '🏢 Main Control Center' },
    { command: 'dashboard', description: '📊 Real-time War-Room progress' },
    { command: 'draft', description: '📝 Draft a new Plan with AI' },
    { command: 'status', description: '💻 List running War-Rooms' },
    { command: 'help', description: '❓ Detailed user guide' },
  ]).catch(err => console.warn('[TELEGRAM] Failed to register commands:', err.message));

  return bot;
}

export function startTelegram(): void {
  const bot = createTelegramBot();
  if (!bot) return;

  console.log(`[TELEGRAM] Starting bot... (pairing code: ${PAIRING_CODE})`);
  bot.launch({ dropPendingUpdates: true });

  // Graceful stop
  process.once('SIGINT', () => bot.stop('SIGINT'));
  process.once('SIGTERM', () => bot.stop('SIGTERM'));
}
