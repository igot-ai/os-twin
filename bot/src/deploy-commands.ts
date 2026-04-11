/**
 * deploy-commands.ts — Register Discord slash commands with the API.
 *
 * Run: npx tsx src/deploy-commands.ts
 */

import dotenv from 'dotenv';
import path from 'path';
import os from 'os';

dotenv.config({ path: path.join(os.homedir(), '.ostwin', '.env') });
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

import { REST, Routes, SlashCommandBuilder } from 'discord.js';

const TOKEN = process.env.DISCORD_TOKEN;
const CLIENT_ID = process.env.DISCORD_CLIENT_ID;
const GUILD_ID = process.env.GUILD_ID;

if (!TOKEN || !CLIENT_ID) {
  console.error('Missing DISCORD_TOKEN or DISCORD_CLIENT_ID in .env');
  process.exit(1);
}

// Shared OS Twin commands
const commands = [
  new SlashCommandBuilder().setName('menu').setDescription('Main Control Center'),
  new SlashCommandBuilder().setName('dashboard').setDescription('Real-time War-Room progress'),
  new SlashCommandBuilder().setName('status').setDescription('List running War-Rooms'),
  new SlashCommandBuilder().setName('compact').setDescription('Latest messages from agents'),
  new SlashCommandBuilder().setName('plans').setDescription('List all project Plans'),
  new SlashCommandBuilder().setName('errors').setDescription('Error summary with root causes'),
  new SlashCommandBuilder().setName('skills').setDescription('View available AI skills'),
  new SlashCommandBuilder().setName('usage').setDescription('Stats report'),
  new SlashCommandBuilder().setName('help').setDescription('Detailed user guide'),
  new SlashCommandBuilder()
    .setName('draft')
    .setDescription('Draft a new Plan with AI')
    .addStringOption(opt => opt.setName('idea').setDescription('Your project idea').setRequired(false)),
  new SlashCommandBuilder().setName('edit').setDescription('Select a plan to edit with AI'),
  new SlashCommandBuilder().setName('assets').setDescription('List assets saved for the active or selected plan'),
  new SlashCommandBuilder().setName('viewplan').setDescription('View a plan\'s content'),
  new SlashCommandBuilder().setName('startplan').setDescription('Select and launch a plan'),
  new SlashCommandBuilder().setName('cancel').setDescription('Exit current editing session'),
  new SlashCommandBuilder().setName('transcribe').setDescription('Transcribe a voice recording and optionally draft a plan'),
  // Notification & Feedback
  new SlashCommandBuilder()
    .setName('feedback')
    .setDescription('Provide feedback on plan steps or rooms')
    .addStringOption(opt => opt.setName('text').setDescription('Your feedback message').setRequired(true)),
  new SlashCommandBuilder().setName('preferences').setDescription('View and update your notification settings'),
  new SlashCommandBuilder().setName('subscriptions').setDescription('Manage event subscriptions'),
  new SlashCommandBuilder().setName('progress').setDescription('Show real-time progress for active plans'),
  // System commands
  new SlashCommandBuilder().setName('new').setDescription('Wipe old War-Room data to start fresh'),
  new SlashCommandBuilder().setName('restart').setDescription('Reboot the Command Center background process'),
  // Voice commands
  new SlashCommandBuilder().setName('join').setDescription('Join your voice channel and stream live audio'),
  new SlashCommandBuilder().setName('leave').setDescription('Disconnect and save all recordings'),
  // Utility
  new SlashCommandBuilder().setName('ping').setDescription('Check bot latency'),
];

const rest = new REST({ version: '10' }).setToken(TOKEN);

(async () => {
  try {
    console.log(`Registering ${commands.length} commands...`);

    const route = GUILD_ID
      ? Routes.applicationGuildCommands(CLIENT_ID, GUILD_ID)
      : Routes.applicationCommands(CLIENT_ID);

    await rest.put(route, { body: commands.map(c => c.toJSON()) });

    console.log(`✅ Successfully registered ${commands.length} commands${GUILD_ID ? ` to guild ${GUILD_ID}` : ' globally'}.`);
  } catch (error) {
    console.error('Failed to register commands:', error);
  }
})();
