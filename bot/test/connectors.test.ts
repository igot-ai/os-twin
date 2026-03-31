import { expect } from 'chai';
import sinon from 'sinon';
import fs from 'fs/promises';
import path from 'path';
import os from 'os';
import { ConnectorRegistry } from '../src/connectors/registry';
import { Platform, Connector, ConnectorConfig, HealthCheckResult, SetupStep, ValidationResult } from '../src/connectors/base';
import { BotResponse } from '../src/commands';

class MockConnector implements Connector {
  public platform: Platform;
  public status: any = 'disconnected';
  constructor(platform: Platform) { this.platform = platform; }
  async start(config: ConnectorConfig): Promise<void> { this.status = 'connected'; }
  async stop(): Promise<void> { this.status = 'disconnected'; }
  async healthCheck(): Promise<HealthCheckResult> { return { status: 'healthy' }; }
  async sendMessage(targetId: string, response: BotResponse): Promise<void> {}
  getSetupInstructions(): SetupStep[] { return []; }
  validateConfig(config: ConnectorConfig): ValidationResult { return { valid: true }; }
}

describe('ConnectorRegistry', () => {
  let registry: ConnectorRegistry;
  let fsReadFile: sinon.SinonStub;
  let fsWriteFile: sinon.SinonStub;
  let fsMkdir: sinon.SinonStub;
  const testConfigPath = path.join(os.tmpdir(), 'channels-test.json');

  beforeEach(() => {
    fsReadFile = sinon.stub(fs, 'readFile');
    fsWriteFile = sinon.stub(fs, 'writeFile');
    fsMkdir = sinon.stub(fs, 'mkdir');
    registry = new ConnectorRegistry({ configPath: testConfigPath });
  });

  afterEach(() => {
    sinon.restore();
  });

  describe('register', () => {
    it('registers a connector', () => {
      const mock = new MockConnector('telegram');
      registry.register(mock);
      expect(registry.getConnector('telegram')).to.equal(mock);
    });
  });

  describe('loadConfigs', () => {
    it('loads configurations from file', async () => {
      const mockConfigs = [
        { platform: 'telegram', enabled: true, credentials: { token: 't1' } }
      ];
      fsReadFile.resolves(JSON.stringify(mockConfigs));

      await registry.loadConfigs();
      const config = registry.getConfig('telegram');
      expect(config?.credentials.token).to.equal('t1');
    });

    it('creates default config if file does not exist', async () => {
      const error = new Error('ENOENT');
      (error as any).code = 'ENOENT';
      fsReadFile.rejects(error);
      fsWriteFile.resolves();
      fsMkdir.resolves();

      await registry.loadConfigs();
      expect(fsWriteFile.calledOnce).to.be.true;
    });
  });

  describe('lifecycle', () => {
    it('starts all enabled connectors', async () => {
      const tgMock = new MockConnector('telegram');
      const dcMock = new MockConnector('discord');
      registry.register(tgMock);
      registry.register(dcMock);

      const mockConfigs = [
        { platform: 'telegram', enabled: true, credentials: { token: 't1' } },
        { platform: 'discord', enabled: false, credentials: { token: 'd1' } }
      ];
      fsReadFile.resolves(JSON.stringify(mockConfigs));

      await registry.loadConfigs();
      await registry.startAll();

      expect(tgMock.status).to.equal('connected');
      expect(dcMock.status).to.equal('disconnected');
    });

    it('stops all connectors', async () => {
      const tgMock = new MockConnector('telegram');
      registry.register(tgMock);
      tgMock.status = 'connected';

      await registry.stopAll();
      expect(tgMock.status).to.equal('disconnected');
    });
  });

  describe('updateConfig', () => {
    it('updates configuration and saves to file', async () => {
      const mockConfigs = [
        { platform: 'telegram', enabled: true, credentials: { token: 't1' } }
      ];
      fsReadFile.resolves(JSON.stringify(mockConfigs));
      fsWriteFile.resolves();

      await registry.loadConfigs();
      await registry.updateConfig('telegram', { enabled: false });

      expect(registry.getConfig('telegram')?.enabled).to.be.false;
      expect(fsWriteFile.calledOnce).to.be.true;
    });

    it('creates new config if platform not exists', async () => {
      fsWriteFile.resolves();
      await registry.updateConfig('slack', { enabled: true });
      expect(registry.getConfig('slack')?.platform).to.equal('slack');
    });
  });

  describe('saveConfigs failure', () => {
    it('throws error if mkdir fails', async () => {
      fsMkdir.rejects(new Error('mkdir failed'));
      try {
        await registry.saveConfigs();
        expect.fail('should have thrown');
      } catch (err: any) {
        expect(err.message).to.equal('mkdir failed');
      }
    });
  });
});
