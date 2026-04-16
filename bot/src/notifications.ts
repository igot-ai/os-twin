import WebSocket from 'ws';
import { ConnectorRegistry } from './connectors/registry';


export type NotificationEvent = 
  | 'plan_started' 
  | 'epic_passed' 
  | 'epic_failed' 
  | 'epic_retry' 
  | 'plan_completed' 
  | 'error' 
  | 'feedback_needed';

export class NotificationRouter {
  private ws: WebSocket | null = null;
  private registry: ConnectorRegistry;
  private url: string;
  private reconnectTimer: NodeJS.Timeout | null = null;

  constructor(registry: ConnectorRegistry, url: string = 'ws://localhost:9000/api/ws') {
    this.registry = registry;
    this.url = url;
  }

  public start() {
    this.connect();
  }

  public stop() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.terminate();
      this.ws = null;
    }
  }

  private connect() {
    console.log(`[NOTIFICATIONS] Connecting to dashboard WebSocket: ${this.url}`);
    this.ws = new WebSocket(this.url);

    this.ws.on('open', () => {
      console.log('[NOTIFICATIONS] Connected to dashboard');
    });

    this.ws.on('message', (data) => {
      try {
        const event = JSON.parse(data.toString());
        this.handleDashboardEvent(event);
      } catch (err) {
        console.error('[NOTIFICATIONS] Failed to parse event:', err);
      }
    });

    this.ws.on('close', () => {
      console.log('[NOTIFICATIONS] Connection closed, reconnecting in 5s...');
      this.scheduleReconnect();
    });

    this.ws.on('error', (err) => {
      console.error('[NOTIFICATIONS] WebSocket error:', err.message);
    });
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this.connect(), 5000);
  }

  private handleDashboardEvent(event: any) {
    const { type, data } = event;
    let notification: NotificationEvent | null = null;
    let messageBody = '';
    let roomId = data?.room?.room_id || data?.room_id;

    switch (type) {
      case 'room_created':
        notification = 'plan_started';
        messageBody = `🚀 *New War-Room Created:* \`${roomId}\`\nTask: ${data.room.task_ref || 'Initial Setup'}`;
        break;

      case 'room_updated':
        const status = data.room.status;
        if (status === 'passed') {
          notification = 'epic_passed';
          messageBody = `✅ *EPIC Passed:* \`${roomId}\`\nAll tasks completed successfully.`;
        } else if (status === 'failed') {
          notification = 'epic_failed';
          messageBody = `❌ *EPIC Failed:* \`${roomId}\`\nInvestigation required.`;
        } else if (status === 'fixing') {
          notification = 'epic_retry';
          messageBody = `🔄 *EPIC Retrying:* \`${roomId}\`\nAddressing QA feedback.`;
        } else if (status === 'pending_feedback') {
          notification = 'feedback_needed';
          messageBody = `🤔 *Feedback Needed:* \`${roomId}\`\nPlease provide input to proceed.`;
        } else if (status === 'error') {
          notification = 'error';
          messageBody = `⚠️ *System Error:* \`${roomId}\`\nCheck logs for details.`;
        }
        break;

      case 'room_removed':
        notification = 'plan_completed';
        messageBody = `🏁 *War-Room Removed:* \`${roomId}\`\nCleaned up successfully.`;
        break;

      case 'plans_updated':
        // Optional: Notify if a whole plan is completed
        break;
    }

    if (notification && messageBody) {
      this.routeNotification(notification, messageBody);
    }
  }

  private async routeNotification(event: NotificationEvent, text: string) {
    const configs = this.registry.getAllConfigs();
    
    for (const config of configs) {
      if (!config.enabled) continue;
      
      const prefs = config.notification_preferences;
      if (!prefs.enabled) continue;
      
      // If events list is empty, treat as "all enabled" or check specific mapping
      if (prefs.events.length > 0 && !prefs.events.includes(event)) {
        continue;
      }

      const connector = this.registry.getConnector(config.platform);
      if (connector && connector.status === 'connected') {
        for (const userId of config.authorized_users) {
          try {
            await connector.sendMessage(userId, { text });
          } catch (err) {
            console.error(`[NOTIFICATIONS] Failed to send to ${config.platform}:${userId}:`, err);
          }
        }
      }
    }
  }
}
