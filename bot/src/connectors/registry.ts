import fs from 'fs/promises';
import path from 'path';
import os from 'os';
import { Platform, Connector, ConnectorConfig, HealthCheckResult } from './base';

export interface ConnectorRegistryConfig {
  configPath?: string;
}

export class ConnectorRegistry {
  private connectors: Map<Platform, Connector> = new Map();
  private configs: Map<Platform, ConnectorConfig> = new Map();
  private configPath: string;

  constructor(options: ConnectorRegistryConfig = {}) {
    this.configPath = options.configPath || path.join(os.homedir(), '.ostwin', 'channels.json');
  }

  public register(connector: Connector): void {
    this.connectors.set(connector.platform, connector);
  }

  public async loadConfigs(): Promise<void> {
    try {
      const data = await fs.readFile(this.configPath, 'utf-8');
      const loadedConfigs: ConnectorConfig[] = JSON.parse(data);
      this.configs.clear();
      for (const config of loadedConfigs) {
        this.configs.set(config.platform, config);
      }
    } catch (error: any) {
      if (error.code === 'ENOENT') {
        // Create default empty config if it doesn't exist
        await this.saveConfigs();
      } else {
        console.error(`[REGISTRY] Failed to load configs: ${error.message}`);
        throw error;
      }
    }
  }

  public async saveConfigs(): Promise<void> {
    try {
      const dir = path.dirname(this.configPath);
      await fs.mkdir(dir, { recursive: true });
      const configList = Array.from(this.configs.values());
      await fs.writeFile(this.configPath, JSON.stringify(configList, null, 2), 'utf-8');
    } catch (error: any) {
      console.error(`[REGISTRY] Failed to save configs: ${error.message}`);
      throw error;
    }
  }

  public async startAll(): Promise<void> {
    const promises = Array.from(this.connectors.entries()).map(async ([platform, connector]) => {
      const config = this.configs.get(platform);
      if (config && config.enabled) {
        try {
          console.log(`[REGISTRY] Starting ${platform} connector...`);
          await connector.start(config);
        } catch (error: any) {
          console.error(`[REGISTRY] Failed to start ${platform} connector: ${error.message}`);
        }
      } else {
        console.log(`[REGISTRY] ${platform} connector is disabled or missing config.`);
      }
    });

    await Promise.allSettled(promises);
  }

  public async stopAll(): Promise<void> {
    for (const connector of this.connectors.values()) {
      try {
        await connector.stop();
      } catch (error: any) {
        console.error(`[REGISTRY] Failed to stop ${connector.platform} connector: ${error.message}`);
      }
    }
  }

  public getConnector(platform: Platform): Connector | undefined {
    return this.connectors.get(platform);
  }

  public getConfig(platform: Platform): ConnectorConfig | undefined {
    return this.configs.get(platform);
  }

  public getAllConfigs(): ConnectorConfig[] {
    return Array.from(this.configs.values());
  }

  public async updateConfig(platform: Platform, config: Partial<ConnectorConfig>): Promise<void> {
    const existing = this.configs.get(platform) || {
      platform,
      enabled: false,
      credentials: {},
      settings: {},
      authorized_users: [],
      pairing_code: '',
      notification_preferences: { events: [], enabled: true },
    };
    this.configs.set(platform, { ...existing, ...config } as ConnectorConfig);
    await this.saveConfigs();
  }

  public async getHealth(): Promise<Record<Platform, HealthCheckResult>> {
    const health: Record<string, HealthCheckResult> = {};
    for (const [platform, connector] of this.connectors) {
      health[platform] = await connector.healthCheck();
    }
    return health as Record<Platform, HealthCheckResult>;
  }
}

// Singleton for easy access in commands
export const registry = new ConnectorRegistry();

