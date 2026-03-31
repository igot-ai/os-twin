import { TelegramConnector } from './connectors/telegram';
import config from './config';

/** @deprecated Use TelegramConnector class */
export function createTelegramBot(): any {
  if (!config.TELEGRAM_BOT_TOKEN) return null;
  const connector = new TelegramConnector();
  connector.start({
    platform: 'telegram',
    enabled: true,
    credentials: {
      token: config.TELEGRAM_BOT_TOKEN,
    },
    settings: {},
    authorized_users: [],
    pairing_code: '',
    notification_preferences: { events: [], enabled: true },
  }).catch(() => {});
  
  return connector.bot;
}

/** @deprecated Use TelegramConnector class */
export function startTelegram(): void {
  console.warn('startTelegram is deprecated. Use TelegramConnector via ConnectorRegistry instead.');
}
