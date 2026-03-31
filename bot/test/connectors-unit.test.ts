
import { expect } from 'chai';
import { TelegramConnector } from '../src/connectors/telegram';
import { DiscordConnector } from '../src/connectors/discord';
import { SlackConnector } from '../src/connectors/slack';

describe('Connectors Unit Tests', () => {
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
      (connector as any).bot = { stop: () => {} };
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
      (connector as any).client = { destroy: () => {} };
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
      (connector as any).app = { stop: async () => {} };
      connector.status = 'connected';
      await connector.stop();
      expect(connector.status).to.equal('disconnected');
      expect(connector.app).to.be.null;
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
