import { App, SayFn, RespondFn, BlockAction, SlackAction, SlackActionMiddlewareArgs, SlashCommand } from '@slack/bolt';
import { Platform, Connector, ConnectorConfig, ConnectorStatus, HealthCheckResult, SetupStep, ValidationResult } from './base';
import { routeCommand, routeCallback, handleStatefulText, BotResponse } from '../commands';
import { getSession } from '../sessions';
import { chunk } from './utils';

const SLACK_MSG_LIMIT = 3000;

export class SlackConnector implements Connector {
  public readonly platform: Platform = 'slack';
  public status: ConnectorStatus = 'disconnected';
  private app: App | null = null;
  private authorizedUsers: Set<string> = new Set();
  private pairingCode: string = '';

  public async start(config: ConnectorConfig): Promise<void> {
    const token = config.credentials.token;
    const appToken = config.credentials.appToken;
    const signingSecret = config.credentials.signingSecret;

    if (!token || !appToken) {
      this.status = 'error';
      throw new Error('Slack token or appToken is missing in credentials');
    }

    this.status = 'connecting';
    this.pairingCode = config.pairing_code || Math.random().toString(16).slice(2, 10);
    this.authorizedUsers = new Set(config.authorized_users || []);

    this.app = new App({
      token,
      appToken,
      signingSecret,
      socketMode: true,
    });

    // ── Middleware: Authorization ─────────────────────────────────
    this.app.use(async ({ body, context, next }) => {
      // Body can be many things, try to extract user id
      const userId = (body as any).user_id || (body as any).user?.id;
      
      // Allow if it's a slash command /pair
      if ((body as any).command === '/pair') return next!();

      // Check authorization (allow if no users configured yet = first user)
      if (this.authorizedUsers.size > 0 && userId && !this.authorizedUsers.has(userId)) {
        // We can't easily reply here without more context, but Bolt's built-in 
        // listeners can handle it. For middleware, we just check.
      }

      await next!();
    });

    // ── Slash Commands ────────────────────────────────────────────
    
    // /pair command
    this.app.command('/pair', async ({ command, ack, respond }) => {
      await ack();
      const userId = command.user_id;
      const args = command.text.trim();
      if (args === this.pairingCode) {
        this.authorizedUsers.add(userId);
        await respond({
          text: `✅ *Pairing successful!* <@${userId}> is now authorized.`,
          response_type: 'ephemeral'
        });
      } else {
        await respond({
          text: `❌ *Invalid pairing code.*`,
          response_type: 'ephemeral'
        });
      }
    });

    // Main /ostwin command
    this.app.command('/ostwin', async ({ command, ack, say, respond }) => {
      await ack();
      const userId = command.user_id;
      if (!this.isAuthorized(userId)) {
        await this.sendUnauthorized(respond, userId);
        return;
      }

      const text = command.text.trim();
      const [cmd, ...args] = text.split(/\s+/);
      const responses = await routeCommand(userId, 'slack', cmd || 'menu', args.join(' '));
      await this.sendResponses(say, userId, responses);
    });

    // Shortcuts
    const SHORTCUTS = ['draft', 'status', 'dashboard'] as const;
    for (const sc of SHORTCUTS) {
      this.app.command(`/${sc}`, async ({ command, ack, say, respond }) => {
        await ack();
        const userId = command.user_id;
        if (!this.isAuthorized(userId)) {
          await this.sendUnauthorized(respond, userId);
          return;
        }
        const args = command.text.trim();
        const responses = await routeCommand(userId, 'slack', sc, args);
        await this.sendResponses(say, userId, responses);
      });
    }

    // Other commands as separate slash commands if registered in Slack
    const OTHER_COMMANDS = [
      'menu', 'compact', 'plans', 'errors', 'skills', 'usage', 'help', 'start', 'cancel', 'edit', 'startplan', 'viewplan'
    ];
    for (const cmd of OTHER_COMMANDS) {
      this.app.command(`/${cmd}`, async ({ command, ack, say, respond }) => {
        await ack();
        const userId = command.user_id;
        if (!this.isAuthorized(userId)) {
          await this.sendUnauthorized(respond, userId);
          return;
        }
        const responses = await routeCommand(userId, 'slack', cmd);
        await this.sendResponses(say, userId, responses);
      });
    }

    // ── Action Handlers (Buttons) ─────────────────────────────────
    
    // Match any action_id starting with menu: or cmd:
    this.app.action(/^(menu|cmd):/, async ({ action, ack, body }) => {
      await ack();
      const userId = body.user.id;
      if (!this.isAuthorized(userId)) return;

      const actionId = (action as any).action_id;
      const responses = await routeCallback(userId, 'slack', actionId);
      
      // If the action happened in a thread, reply in that thread
      const channelId = (body as any).channel?.id;
      const threadTs = (body as any).message?.thread_ts || (body as any).message?.ts;
      
      if (channelId) {
        await this.sendResponsesChat(channelId, responses, threadTs);
      }
    });

    // ── Free Text & Thread Replies ────────────────────────────────

    this.app.message(async ({ message, say }) => {
      // Only handle non-bot messages
      if ((message as any).bot_id) return;
      
      const userId = (message as any).user;
      const text = (message as any).text?.trim();
      if (!userId || !text) return;

      // Skip if it's a slash command (Bolt usually doesn't trigger 'message' for commands anyway)
      if (text.startsWith('/')) return;

      if (!this.isAuthorized(userId)) return;

      const session = getSession(userId, 'slack');
      
      // Only handle if in a stateful mode
      if (session.mode === 'idle') return;

      // If in a thread, use that thread. If not, use the message ts to start/continue a thread.
      const threadTs = (message as any).thread_ts || (message as any).ts;
      
      const responses = await handleStatefulText(userId, 'slack', text);
      await this.sendResponses(say, userId, responses, threadTs);
    });

    await this.app.start();
    this.status = 'connected';
    console.log('[SLACK] Connector started successfully with Socket Mode');
  }

  public async stop(): Promise<void> {
    if (this.app) {
      await this.app.stop();
      this.app = null;
    }
    this.status = 'disconnected';
  }

  public async healthCheck(): Promise<HealthCheckResult> {
    if (this.status === 'connected') {
      return { status: 'healthy', message: 'Connected and listening via Socket Mode' };
    }
    return { status: 'unhealthy', message: `Status: ${this.status}` };
  }

  public async sendMessage(targetId: string, response: BotResponse): Promise<void> {
    if (!this.app) throw new Error('Slack app not started');
    await this.sendResponsesChat(targetId, [response]);
  }

  public getSetupInstructions(): SetupStep[] {
    return [
      {
        title: 'Create Slack App',
        description: 'Create an app at api.slack.com/apps',
        instructions: '1. Enable Socket Mode\n2. Add Slash Commands (/ostwin, /draft, etc.)\n3. Add Bot Token Scopes (chat:write, commands, im:history)\n4. Generate an App-Level Token with connections:write scope'
      }
    ];
  }

  public validateConfig(config: ConnectorConfig): ValidationResult {
    const errors: string[] = [];
    if (!config.credentials.token) errors.push('Missing Bot Token');
    if (!config.credentials.appToken) errors.push('Missing App-Level Token');
    return { valid: errors.length === 0, errors };
  }

  // ── Helpers ─────────────────────────────────────────────────────

  private isAuthorized(userId: string): boolean {
    return this.authorizedUsers.size === 0 || this.authorizedUsers.has(userId);
  }

  private async sendUnauthorized(respond: RespondFn, userId: string) {
    await respond({
      text: `🔒 *Unauthorized.* This bot is private. Use \`/pair ${this.pairingCode}\` to authorize.`,
      response_type: 'ephemeral'
    });
  }

  private async sendResponses(say: SayFn, userId: string, responses: BotResponse[], threadTs?: string) {
    for (const resp of responses) {
      const messagePayload = this.translateResponse(resp);
      if (threadTs) {
        messagePayload.thread_ts = threadTs;
      }
      await say(messagePayload);
    }
  }

  private async sendResponsesChat(chatId: string, responses: BotResponse[], threadTs?: string) {
    if (!this.app) return;
    for (const resp of responses) {
      const payload = this.translateResponse(resp);
      await this.app.client.chat.postMessage({
        channel: chatId,
        thread_ts: threadTs,
        ...payload
      });
    }
  }

  private translateResponse(resp: BotResponse): any {
    const blocks: any[] = [];
    
    // Add text blocks with chunking
    if (resp.text) {
      const formatted = this.formatMrkdwn(resp.text);
      const chunks = chunk(formatted, SLACK_MSG_LIMIT);
      for (const c of chunks) {
        blocks.push({
          type: 'section',
          text: {
            type: 'mrkdwn',
            text: c
          }
        });
      }
    }

    // Add button blocks
    if (resp.buttons && resp.buttons.length > 0) {
      for (const row of resp.buttons) {
        const elements = row.map(btn => ({
          type: 'button',
          text: {
            type: 'plain_text',
            text: btn.label
          },
          action_id: btn.callbackData
        }));
        
        blocks.push({
          type: 'actions',
          elements
        });
      }
    }

    return {
      text: resp.text, // Fallback text
      blocks
    };
  }

  private formatMrkdwn(text: string): string {
    // Slack mrkdwn is slightly different from standard Markdown
    // Bold: *text* (same)
    // Italic: _text_ (same)
    // Link: <url|label> (different)
    
    // Simple translation for common patterns
    return text
      .replace(/\*\*(.*?)\*\*/g, '*$1*') // **bold** -> *bold*
      .replace(/\[(.*?)\]\((.*?)\)/g, '<$2|$1>'); // [label](url) -> <url|label>
  }
}
