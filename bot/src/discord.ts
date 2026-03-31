import { DiscordConnector } from './connectors/discord';
import { mdConvert as _mdConvert, chunk as _chunk } from './connectors/utils';
import config from './config';

/** @deprecated Use DiscordConnector class */
export function createDiscordBot(): any {
  if (!config.DISCORD_TOKEN) return null;
  const connector = new DiscordConnector();
  connector.start({
    platform: 'discord',
    enabled: true,
    credentials: {
      token: config.DISCORD_TOKEN,
      client_id: config.DISCORD_CLIENT_ID || 'fake',
    },
    settings: {},
    authorized_users: [],
    pairing_code: '',
    notification_preferences: { events: [], enabled: true },
  }).catch(() => {}); 
  
  return connector.client;
}

/** @deprecated Use DiscordConnector class */
export function startDiscord(): void {
  console.warn('startDiscord is deprecated. Use DiscordConnector via ConnectorRegistry instead.');
}

/** @deprecated Use standalone mdConvert or new architecture */
export const mdConvert = _mdConvert;
/** @deprecated Use standalone chunk or new architecture */
export const chunk = _chunk;
