/**
 * telegram.ts — Telegram bot adapter using Telegraf.
 *
 * Handles: long-polling, inline keyboards, callback queries, authorization.
 * Delegates all command logic to commands.ts.
 */

import { Telegraf, Markup, Context } from 'telegraf';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import config from './config';
import { routeCommand, routeCallback, handleStatefulText, BotResponse } from './commands';
import { getSession } from './sessions';

/** Authorized chat IDs (loaded from env or paired at runtime) */
const authorizedChats = new Set<string>();
const PAIRING_CODE = process.env.TELEGRAM_PAIRING_CODE || crypto.randomBytes(4).toString('hex');

const AUTHORIZED_CHATS_FILE = path.resolve(__dirname, '../.authorized-chats.json');

function loadAuthorizedChats(): void {
  const envChatId = process.env.TELEGRAM_CHAT_ID;
  if (envChatId) authorizedChats.add(String(envChatId));
  try {
    if (fs.existsSync(AUTHORIZED_CHATS_FILE)) {
      const data = JSON.parse(fs.readFileSync(AUTHORIZED_CHATS_FILE, 'utf-8'));
      if (Array.isArray(data)) data.forEach((id: string) => authorizedChats.add(String(id)));
    }
  } catch { /* ignore corrupt file */ }
}

function persistAuthorizedChats(): void {
  try {
    fs.writeFileSync(AUTHORIZED_CHATS_FILE, JSON.stringify([...authorizedChats]), 'utf-8');
  } catch (err) {
    console.warn('[TELEGRAM] Failed to persist authorized chats:', err);
  }
}

// ── Message splitting for Telegram's 4096 char limit ──────────────

const TELEGRAM_MAX_LENGTH = 4096;

function splitMessage(text: string): string[] {
  if (text.length <= TELEGRAM_MAX_LENGTH) return [text];
  const chunks: string[] = [];
  let remaining = text;
  while (remaining.length > 0) {
    if (remaining.length <= TELEGRAM_MAX_LENGTH) {
      chunks.push(remaining);
      break;
    }
    let splitAt = remaining.lastIndexOf('\n', TELEGRAM_MAX_LENGTH);
    if (splitAt < TELEGRAM_MAX_LENGTH / 2) splitAt = TELEGRAM_MAX_LENGTH;
    chunks.push(remaining.slice(0, splitAt));
    remaining = remaining.slice(splitAt);
  }
  return chunks;
}

// ── Response renderer ─────────────────────────────────────────────

function buildMarkup(buttons: BotResponse['buttons']) {
  if (!buttons?.length) return {};
  const keyboard = buttons.map(row =>
    row.map(btn => Markup.button.callback(btn.label, btn.callbackData))
  );
  return Markup.inlineKeyboard(keyboard);
}

async function sendResponses(ctx: Context, responses: BotResponse[]): Promise<void> {
  for (const resp of responses) {
    const extra = { parse_mode: 'Markdown' as const, ...buildMarkup(resp.buttons) };
    for (const chunk of splitMessage(resp.text)) {
      await ctx.reply(chunk, extra);
    }
  }
}

async function sendResponsesChat(bot: Telegraf, chatId: string, responses: BotResponse[]): Promise<void> {
  for (const resp of responses) {
    const extra = { parse_mode: 'Markdown' as const, ...buildMarkup(resp.buttons) };
    for (const chunk of splitMessage(resp.text)) {
      await bot.telegram.sendMessage(chatId, chunk, extra);
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

  loadAuthorizedChats();

  // ── Authorization middleware ──────────────────────────────────
  bot.use(async (ctx, next) => {
    if (!ctx.chat?.id) return;
    const chatId = String(ctx.chat.id);

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
      persistAuthorizedChats();
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
      try {
        await ctx.sendChatAction('typing');
        const userId = String(ctx.chat.id);
        const responses = await routeCommand(userId, 'telegram', cmd);
        await sendResponses(ctx, responses);
      } catch (err) {
        console.error(`[TELEGRAM] Error in /${cmd}:`, err);
        await ctx.reply('⚠️ Something went wrong. Please try again.').catch(() => {});
      }
    });
  }

  // /draft with optional inline argument
  bot.command('draft', async (ctx) => {
    try {
      await ctx.sendChatAction('typing');
      const userId = String(ctx.chat.id);
      const args = ctx.message.text.replace(/^\/draft(@\S+)?/, '').trim();
      const responses = await routeCommand(userId, 'telegram', 'draft', args);
      await sendResponses(ctx, responses);
    } catch (err) {
      console.error('[TELEGRAM] Error in /draft:', err);
      await ctx.reply('⚠️ Something went wrong. Please try again.').catch(() => {});
    }
  });

  // ── Callback queries (inline keyboard buttons) ────────────────
  bot.on('callback_query', async (ctx) => {
    try {
      const cbQuery = ctx.callbackQuery;
      const chatId = 'message' in cbQuery ? cbQuery.message?.chat?.id : undefined;
      const data = 'data' in cbQuery ? cbQuery.data : undefined;
      if (!chatId || !data) return;

      const userId = String(chatId);
      await ctx.answerCbQuery();

      const responses = await routeCallback(userId, 'telegram', data);

      // Try editing the original message for menu navigation, fall back to new message
      if (responses.length === 1 && data.startsWith('menu:')) {
        try {
          const extra = { parse_mode: 'Markdown' as const, ...buildMarkup(responses[0].buttons) };
          await ctx.editMessageText(responses[0].text, extra);
          return;
        } catch {
          // Edit failed (message too old, same content, etc.) — fall through to send
        }
      }

      await sendResponsesChat(bot, userId, responses);
    } catch (err) {
      console.error('[TELEGRAM] Error in callback_query:', err);
    }
  });

  // ── Free text (stateful AI editing) ───────────────────────────
  bot.on('text', async (ctx) => {
    try {
      const userId = String(ctx.chat.id);
      const msgText = ctx.message.text.trim();

      if (msgText.startsWith('/')) return;

      const session = getSession(userId, 'telegram');
      if (['drafting', 'editing', 'awaiting_idea'].includes(session.mode)) {
        await ctx.sendChatAction('typing');
        const responses = await handleStatefulText(userId, 'telegram', msgText);
        await sendResponses(ctx, responses);
      } else {
        await ctx.reply('💡 Use /menu to get started, or /help for all commands.', { parse_mode: 'Markdown' });
      }
    } catch (err) {
      console.error('[TELEGRAM] Error in text handler:', err);
      await ctx.reply('⚠️ Something went wrong. Please try again.').catch(() => {});
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
