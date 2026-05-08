/**
 * config.ts — Shared configuration for both bots.
 *
 * Loads env vars from multiple sources (first match wins — dotenv won't overwrite):
 *   1. ~/.ostwin/.env       — global install (API keys, OSTWIN_API_KEY)
 *   2. ./.env               — cwd (where ostwin bot start was run)
 *   3. <bot>/../.env        — project root relative to bot/src/
 *
 * Exported as a mutable object so tests can override values.
 */

import dotenv from 'dotenv';
import path from 'path';
import os from 'os';

// Load global ~/.ostwin/.env first (API keys, OSTWIN_API_KEY)
dotenv.config({ path: path.join(os.homedir(), '.ostwin', '.env') });
// Load from cwd (where the user ran the command)
dotenv.config({ path: path.resolve(process.cwd(), '.env') });
// Load from project root relative to this file (fallback for source repo layout)
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

export interface AppConfig {
  DASHBOARD_URL: string;
  OSTWIN_API_KEY: string;
  TELEGRAM_BOT_TOKEN: string;
  DISCORD_TOKEN: string;
  DISCORD_CLIENT_ID: string;
  GUILD_ID: string;
  SLACK_BOT_TOKEN: string;
  SLACK_APP_TOKEN: string;
  SLACK_SIGNING_SECRET: string;
  GOOGLE_API_KEY: string;
  GEMINI_MODEL: string;
}

const config: AppConfig = {
  DASHBOARD_URL: process.env.DASHBOARD_URL || 'http://localhost:3366',
  OSTWIN_API_KEY: process.env.OSTWIN_API_KEY || '',
  TELEGRAM_BOT_TOKEN: process.env.TELEGRAM_BOT_TOKEN || '',
  DISCORD_TOKEN: process.env.DISCORD_TOKEN || '',
  DISCORD_CLIENT_ID: process.env.DISCORD_CLIENT_ID || '',
  GUILD_ID: process.env.GUILD_ID || '',
  SLACK_BOT_TOKEN: process.env.SLACK_BOT_TOKEN || '',
  SLACK_APP_TOKEN: process.env.SLACK_APP_TOKEN || '',
  SLACK_SIGNING_SECRET: process.env.SLACK_SIGNING_SECRET || '',
  GOOGLE_API_KEY: process.env.GOOGLE_API_KEY || '',
  GEMINI_MODEL: process.env.GEMINI_MODEL || 'gemini-3-flash-preview',
};

export default config;
