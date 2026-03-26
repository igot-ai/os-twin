const client = require('./client');

if (!process.env.DISCORD_TOKEN) {
  console.error('[ERROR] Missing DISCORD_TOKEN. Please set it in your .env file.');
  process.exit(1);
}

// Start the Bot
client.login(process.env.DISCORD_TOKEN).catch(error => {
  console.error('[FATAL] Failed to login to Discord:', error);
  process.exit(1);
});
