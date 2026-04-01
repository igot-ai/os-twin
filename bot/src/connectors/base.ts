import { BotResponse } from '../commands';

export type Platform = 'telegram' | 'discord' | 'slack';

export type ConnectorStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface ConnectorConfig {
  platform: Platform;
  enabled: boolean;
  credentials: Record<string, string>;
  settings: Record<string, any>;
  authorized_users: string[];
  pairing_code: string;
  notification_preferences: {
    events: string[];
    enabled: boolean;
  };
}

export interface HealthCheckResult {
  status: 'healthy' | 'unhealthy' | 'warning';
  message?: string;
  details?: Record<string, any>;
}

export interface SetupStep {
  title: string;
  description: string;
  instructions: string;
}

export interface ValidationResult {
  valid: boolean;
  errors?: string[];
}

export interface Connector {
  readonly platform: Platform;
  status: ConnectorStatus;
  start(config: ConnectorConfig): Promise<void>;
  stop(): Promise<void>;
  healthCheck(): Promise<HealthCheckResult>;
  sendMessage(targetId: string, response: BotResponse): Promise<void>;
  getSetupInstructions(): SetupStep[];
  validateConfig(config: ConnectorConfig): ValidationResult;
}
