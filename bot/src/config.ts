/**
 * config.ts — Shared configuration for both bots.
 *
 * Loads .env from the project root (one level above bot/).
 * Exported as a mutable object so tests can override values.
 */

import dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.resolve(__dirname, '../../.env') });

export interface AppConfig {
  DASHBOARD_URL: string;
  OSTWIN_API_KEY: string;
  TELEGRAM_BOT_TOKEN: string;
  DISCORD_TOKEN: string;
  DISCORD_CLIENT_ID: string;
  GUILD_ID: string;
  GOOGLE_API_KEY: string;
  GEMINI_MODEL: string;
}

const config: AppConfig = {
  DASHBOARD_URL: process.env.DASHBOARD_URL || 'http://localhost:9000',
  OSTWIN_API_KEY: process.env.OSTWIN_API_KEY || '',
  TELEGRAM_BOT_TOKEN: process.env.TELEGRAM_BOT_TOKEN || '',
  DISCORD_TOKEN: process.env.DISCORD_TOKEN || '',
  DISCORD_CLIENT_ID: process.env.DISCORD_CLIENT_ID || '',
  GUILD_ID: process.env.GUILD_ID || '',
  GOOGLE_API_KEY: process.env.GOOGLE_API_KEY || '',
  GEMINI_MODEL: process.env.GEMINI_MODEL || 'gemini-2.0-flash',
};

export default config;
