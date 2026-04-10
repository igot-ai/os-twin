/**
 * sessions.ts — In-memory session manager for both platforms.
 *
 * Sessions are keyed by "platform:userId" to avoid collision.
 */

export type SessionMode = 'idle' | 'editing' | 'drafting' | 'awaiting_idea';

export interface ChatMessage {
  role: string;
  content: string;
}

export interface StagedAttachment {
  data: Uint8Array;
  name: string;
  mimeType: string;
  stagedAt: number;
  epicRef?: string;
}

export interface Session {
  userId: string;
  platform: string;
  activePlanId: string | null;
  mode: SessionMode;
  chatHistory: ChatMessage[];
  lastActivity: number;
  lastTranscription?: string;
  workingDir?: string;
  activeEpicRef?: string;
  pendingAttachments: StagedAttachment[];
}

const SESSION_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes

const sessions = new Map<string, Session>();

function _key(userId: string | number, platform: string): string {
  return `${platform}:${userId}`;
}

function _newSession(userId: string | number, platform: string): Session {
  return {
    userId: String(userId),
    platform,
    activePlanId: null,
    mode: 'idle',
    chatHistory: [],
    lastActivity: Date.now(),
    pendingAttachments: [],
  };
}

export function getSession(userId: string | number, platform = 'telegram'): Session {
  const key = _key(userId, platform);
  const now = Date.now();
  let session = sessions.get(key);

  if (session) {
    if (now - session.lastActivity > SESSION_TIMEOUT_MS) {
      session = _newSession(userId, platform);
      sessions.set(key, session);
    } else {
      session.lastActivity = now;
    }
  } else {
    session = _newSession(userId, platform);
    sessions.set(key, session);
  }

  return session;
}

export function clearSession(userId: string | number, platform = 'telegram'): void {
  const key = _key(userId, platform);
  sessions.set(key, _newSession(userId, platform));
}

export function setMode(userId: string | number, platform: string, mode: SessionMode): void {
  const session = getSession(userId, platform);
  session.mode = mode;
  session.lastActivity = Date.now();
}

export function setPlan(userId: string | number, platform: string, planId: string): void {
  const session = getSession(userId, platform);
  session.activePlanId = planId;
  session.lastActivity = Date.now();
}

export function setWorkingDir(userId: string | number, platform: string, dir: string): void {
  const session = getSession(userId, platform);
  session.workingDir = dir;
  session.lastActivity = Date.now();
}
