const { SlashCommandBuilder } = require('discord.js');
const { getVoiceConnection } = require('@discordjs/voice');
const path = require('node:path');
const { cleanupSession } = require('./join');

module.exports = {
  data: new SlashCommandBuilder()
    .setName('leave')
    .setDescription('Disconnects the bot from the voice channel and saves all recordings.'),
  async execute(interaction) {
    const guildId = interaction.guildId;
    const connection = getVoiceConnection(guildId);

    if (!connection) {
      return interaction.reply({ content: "I'm not in a voice channel!", flags: 64 });
    }

    const { saved } = await cleanupSession(guildId);

    const fileList = saved.length
      ? saved.map(f => `\`${path.basename(f)}\``).join(', ')
      : 'No audio was recorded.';

    console.log(`👋 [LEAVE] Disconnected from guild ${guildId}, saved ${saved.length} file(s)`);
    await interaction.reply({
      content: `Disconnected and saved recordings. 👋\n📁 ${fileList}`,
    });
  },
};

