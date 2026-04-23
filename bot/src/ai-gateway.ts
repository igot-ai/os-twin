/**
 * ai-gateway.ts — Unified AI client for the bot.
 *
 * Calls the dashboard's /api/ai/* endpoints (same server the bot already
 * talks to for plans, rooms, etc.).  Replaces direct @google/generative-ai
 * usage so the bot is provider-agnostic.
 *
 * The gateway routes completion calls through litellm on the server side,
 * which translates function-calling format across Gemini/Claude/GPT.
 */

import config from './config';

const BASE = config.DASHBOARD_URL;

function getHeaders(): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (config.OSTWIN_API_KEY) h['X-API-Key'] = config.OSTWIN_API_KEY;
  return h;
}

// ── Types ──────────────────────────────────────────────────────────────

export interface ToolCall {
  id: string;
  function: { name: string; arguments: string };
}

export interface Message {
  role: 'system' | 'user' | 'assistant' | 'tool';
  /** Text content or multimodal parts (e.g. base64 audio/image + text). */
  content?: string | Array<Record<string, unknown>> | null;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}

export interface ToolDeclaration {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

export interface CompleteRequest {
  prompt?: string;
  messages?: Message[];
  model?: string;
  purpose?: string;
  system?: string;
  tools?: ToolDeclaration[];
  response_format?: Record<string, unknown>;
  max_tokens?: number;
  temperature?: number;
}

export interface CompleteResponse {
  text: string | null;
  tool_calls: ToolCall[] | null;
  model: string;
  usage?: { input_tokens: number; output_tokens: number };
}

// ── Completion ──────────────────────────────────────────────────────────

/**
 * Full completion call — supports prompt, messages, and function calling.
 * Returns text, tool_calls, or both.
 */
export async function complete(req: CompleteRequest): Promise<CompleteResponse> {
  const resp = await fetch(`${BASE}/api/ai/complete`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(req),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(`AI Gateway: ${(err as Record<string, string>).detail || resp.statusText}`);
  }
  return resp.json() as Promise<CompleteResponse>;
}

/**
 * Simple prompt → text (no tools, no multi-turn).
 */
export async function getCompletion(
  prompt: string,
  options: Omit<CompleteRequest, 'prompt' | 'messages' | 'tools'> = {},
): Promise<string> {
  const result = await complete({ prompt, ...options });
  return result.text || '';
}

// ── Embedding ───────────────────────────────────────────────────────────

export async function getEmbedding(
  texts: string[],
  model?: string,
): Promise<number[][]> {
  const body: Record<string, unknown> = { texts };
  if (model) body.model = model;

  const resp = await fetch(`${BASE}/api/ai/embed`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(`AI Gateway: ${(err as Record<string, string>).detail || resp.statusText}`);
  }
  const data = await resp.json() as { vectors: number[][] };
  return data.vectors;
}
