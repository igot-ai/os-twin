require('dotenv').config();
const { REST, Routes } = require('discord.js');
const fs = require('fs');
const path = require('path');

if (!process.env.DISCORD_TOKEN) {
  console.error('Error: DISCORD_TOKEN is not set in .env');
  process.exit(1);
}
if (!process.env.DISCORD_CLIENT_ID) {
  console.error('Error: DISCORD_CLIENT_ID is not set in .env');
  process.exit(1);
}

const commands = [];
const commandsPath = path.join(__dirname, 'commands');
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'));

for (const file of commandFiles) {
  const command = require(path.join(commandsPath, file));
  if ('data' in command && 'execute' in command) {
    commands.push(command.data.toJSON());
  }
}

if (commands.length === 0) {
  console.warn('Warning: No commands found to register.');
}

const rest = new REST().setToken(process.env.DISCORD_TOKEN);
const scope = process.env.GUILD_ID ? 'guild' : 'global';

(async () => {
  try {
    console.log(`Started refreshing ${commands.length} ${scope} application (/) commands.`);

    const data = await rest.put(
      process.env.GUILD_ID
        ? Routes.applicationGuildCommands(process.env.DISCORD_CLIENT_ID, process.env.GUILD_ID)
        : Routes.applicationCommands(process.env.DISCORD_CLIENT_ID),
      { body: commands },
    );

    console.log(`Successfully reloaded ${data.length} ${scope} application (/) commands.`);
  } catch (error) {
    console.error('Failed to deploy commands:', error);
    process.exit(1);
  }
})();
