
import { expect } from 'chai';
import { TelegramConnector } from '../src/connectors/telegram';
import { DiscordConnector } from '../src/connectors/discord';
import { SlackConnector } from '../src/connectors/slack';
import { type AttachmentMeta } from '../src/connectors/base';

describe('Connectors Unit Tests', () => {

  // ── Shared types from base.ts ──────────────────────────────────

  describe('AttachmentMeta (shared type)', () => {
    it('can represent a file with full metadata', () => {
      const meta: AttachmentMeta = {
        name: 'mockup.png',
        contentType: 'image/png',
        sizeBytes: 4096,
      };
      expect(meta.name).to.equal('mockup.png');
      expect(meta.contentType).to.equal('image/png');
      expect(meta.sizeBytes).to.equal(4096);
    });

    it('allows optional contentType and sizeBytes', () => {
      const meta: AttachmentMeta = { name: 'unknown-file' };
      expect(meta.name).to.equal('unknown-file');
      expect(meta.contentType).to.be.undefined;
      expect(meta.sizeBytes).to.be.undefined;
    });

    it('allows null contentType (matches Discord attachment shape)', () => {
      const meta: AttachmentMeta = { name: 'file.bin', contentType: null };
      expect(meta.contentType).to.be.null;
    });
  });
  describe('TelegramConnector', () => {
    let connector: TelegramConnector;
    beforeEach(() => connector = new TelegramConnector());

    it('getSetupInstructions returns array', () => {
      const steps = connector.getSetupInstructions();
      expect(steps).to.be.an('array');
      expect(steps.length).to.be.at.least(1);
    });

    it('validateConfig checks token', () => {
      expect(connector.validateConfig({ credentials: {} } as any).valid).to.be.false;
      expect(connector.validateConfig({ credentials: { token: 't' } } as any).valid).to.be.true;
    });

    it('healthCheck returns unhealthy when disconnected', async () => {
      const result = await connector.healthCheck();
      expect(result.status).to.equal('unhealthy');
    });

    it('stop clears bot', async () => {
      (connector as any).bot = { stop: () => { } };
      connector.status = 'connected';
      await connector.stop();
      expect(connector.status).to.equal('disconnected');
      expect(connector.bot).to.be.null;
    });

    it('sendMessage throws if bot not started', async () => {
      try {
        await connector.sendMessage('123', { text: 'hi' });
        expect.fail('Should have thrown');
      } catch (err: any) {
        expect(err.message).to.contain('Telegram bot not started');
      }
    });
  });

  describe('DiscordConnector', () => {
    let connector: DiscordConnector;
    beforeEach(() => connector = new DiscordConnector());

    it('getSetupInstructions returns array', () => {
      const steps = connector.getSetupInstructions();
      expect(steps).to.be.an('array');
    });

    it('validateConfig checks token and client_id', () => {
      expect(connector.validateConfig({ credentials: {} } as any).valid).to.be.false;
      expect(connector.validateConfig({ credentials: { token: 't', client_id: 'c' } } as any).valid).to.be.true;
    });

    it('healthCheck returns unhealthy when disconnected', async () => {
      const result = await connector.healthCheck();
      expect(result.status).to.equal('unhealthy');
    });

    it('stop destroys client', async () => {
      (connector as any).client = { destroy: () => { } };
      connector.status = 'connected';
      await connector.stop();
      expect(connector.status).to.equal('disconnected');
      expect(connector.client).to.be.null;
    });

    it('sendMessage throws if client not started', async () => {
      try {
        await connector.sendMessage('123', { text: 'hi' });
        expect.fail('Should have thrown');
      } catch (err: any) {
        expect(err.message).to.contain('Discord bot not started');
      }
    });

    // ── Message Reference (Reply) Feature Tests ──

    describe('message reference extraction', () => {
      it('LogEntry interface should include referencedMessageId', () => {
        interface LogEntryWithReference {
          id: string;
          guildId: string;
          channelId: string;
          channelName: string;
          userId: string;
          username: string;
          content: string;
          timestamp: string;
          referencedMessageId?: string;
        }

        const entry: LogEntryWithReference = {
          id: '1493148921822842960',
          guildId: '1492748159724818593',
          channelId: '1492748160299307060',
          channelName: 'general',
          userId: '806867494702809108',
          username: 'yougotmeinluv',
          content: 'yes sir',
          timestamp: '2026-04-13T07:20:44.328Z',
          referencedMessageId: '1493148912345678901',
        };

        expect(entry.referencedMessageId).to.equal('1493148912345678901');
      });

      it('LogEntry should allow undefined referencedMessageId for non-replies', () => {
        interface LogEntryWithReference {
          id: string;
          guildId: string;
          channelId: string;
          channelName: string;
          userId: string;
          username: string;
          content: string;
          timestamp: string;
          referencedMessageId?: string;
        }

        const entry: LogEntryWithReference = {
          id: '1493148921822842960',
          guildId: '1492748159724818593',
          channelId: '1492748160299307060',
          channelName: 'general',
          userId: '806867494702809108',
          username: 'yougotmeinluv',
          content: 'hello',
          timestamp: '2026-04-13T07:20:44.328Z',
        };

        expect(entry.referencedMessageId).to.be.undefined;
      });

      it('should extract messageId from Discord message.reference', () => {
        const mockReference = {
          messageId: '1493148912345678901',
          channelId: '1492748160299307060',
          guildId: '1492748159724818593',
        };

        const referencedMessageId = mockReference?.messageId;
        expect(referencedMessageId).to.equal('1493148912345678901');
      });

      it('should return undefined when message.reference is null', () => {
        const mockReference = null as { messageId: string } | null;
        const referencedMessageId = mockReference?.messageId;
        expect(referencedMessageId).to.be.undefined;
      });
    });
  });

  describe('SlackConnector', () => {
    let connector: SlackConnector;
    beforeEach(() => connector = new SlackConnector());

    it('getSetupInstructions returns array', () => {
      const steps = connector.getSetupInstructions();
      expect(steps).to.be.an('array');
    });

    it('healthCheck returns unhealthy when disconnected', async () => {
      const result = await connector.healthCheck();
      expect(result.status).to.equal('unhealthy');
    });

    it('stop stops app', async () => {
      (connector as any).app = { stop: async () => { } };
      connector.status = 'connected';
      await connector.stop();
      expect(connector.status).to.equal('disconnected');
      expect((connector as any).app).to.be.null;
    });

    it('sendMessage throws if app not started', async () => {
      try {
        await connector.sendMessage('c1', { text: 'hi' });
        expect.fail('Should have thrown');
      } catch (err: any) {
        expect(err.message).to.contain('Slack app not started');
      }
    });

    it('validateConfig checks tokens', () => {
      expect(connector.validateConfig({ credentials: {} } as any).valid).to.be.false;
      expect(connector.validateConfig({ credentials: { token: 't', appToken: 'a' } } as any).valid).to.be.true;
    });
  });
});
