/**
 * index.ts — Entry point for the unified OS Twin bot.
 *
 * Starts both Telegram and Discord bots from a single process.
 * Each bot gracefully no-ops if its token is not configured.
 */

// config.ts loads .env from the project root — import it first
import './config';

import { startTelegram } from './telegram';
import { startDiscord } from './discord';

console.log('╔═══════════════════════════════════╗');
console.log('║   OS Twin — Unified Bot Gateway   ║');
console.log('╚═══════════════════════════════════╝');

// Start both bots — each checks its own token
startTelegram();
startDiscord();
