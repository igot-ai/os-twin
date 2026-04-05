/**
 * api.ts — Dashboard API client shared by both bots.
 *
 * All bot commands fetch data from the Python dashboard via these helpers.
 */

import config from './config';

// ── Types ─────────────────────────────────────────────────────────

export interface Plan {
  plan_id: string;
  title?: string;
  status?: string;
  epic_count?: number;
  pct_complete?: number;
  content?: string;
}

export interface PlanAsset {
  plan_id?: string;
  filename: string;
  original_name: string;
  mime_type: string;
  uploaded_at: string;
  size_bytes?: number;
  path?: string;
}

export interface Room {
  room_id: string;
  status: string;
  message_count: number;
  epic_ref?: string;
}

export interface RoomMessage {
  from?: string;
  body?: string;
  type?: string;
  room_id?: string;
}

export interface RoomsSummary {
  total?: number;
  passed?: number;
  failed_final?: number;
  pending?: number;
  engineering?: number;
  qa_review?: number;
  fixing?: number;
}

export interface StatsValue {
  value: number;
}

export interface Stats {
  total_plans?: StatsValue;
  active_epics?: StatsValue;
  completion_rate?: StatsValue;
  escalations_pending?: StatsValue;
  _error?: string;
}

export interface Skill {
  name: string;
  tags?: string[];
}

export interface PlansResult {
  plans: Plan[];
  count?: number;
  error?: string;
}

export interface RoomsResult {
  rooms: Room[];
  summary: RoomsSummary;
  error?: string;
}

export interface RefineResult {
  plan?: string;
  refined_plan?: string;
  explanation?: string;
  raw_result?: {
    plan_id?: string;
    full_response?: string;
  };
  _error?: string;
}

export interface CreateResult {
  plan_id?: string;
  _error?: string;
}

export interface PlanAssetsResult {
  plan_id?: string;
  assets: PlanAsset[];
  count?: number;
  error?: string;
}

// ── Helpers ───────────────────────────────────────────────────────

function getHeaders(contentType: string | null = 'application/json'): Record<string, string> {
  const h: Record<string, string> = {};
  if (contentType) h['Content-Type'] = contentType;
  if (config.OSTWIN_API_KEY) h['X-API-Key'] = config.OSTWIN_API_KEY;
  return h;
}

async function fetchJSON(path: string, options: RequestInit = {}): Promise<any> {
  try {
    const { headers: customHeaders, ...restOptions } = options;
    const res = await fetch(`${config.DASHBOARD_URL}${path}`, {
      ...restOptions,
      headers: customHeaders
        ? { ...getHeaders(null), ...(customHeaders as Record<string, string>) }
        : getHeaders(),
    });
    if (!res.ok) {
      console.warn(`[API] ${path} returned ${res.status}`);
      return { _error: `API returned ${res.status}` };
    }
    const ct = res.headers.get('content-type') || '';
    if (!ct.includes('application/json')) {
      console.warn(`[API] ${path} returned non-JSON content-type: ${ct}`);
      return { _error: `API returned non-JSON response` };
    }
    return await res.json();
  } catch (err: any) {
    console.warn(`[API] Failed to fetch ${path}: ${err.message}`);
    return { _error: `Dashboard unreachable: ${err.message}` };
  }
}

async function postJSON(path: string, body: unknown): Promise<any> {
  return fetchJSON(path, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ── Tunnel / base URL ────────────────────────────────────────────

async function getTunnelStatus(): Promise<{ active: boolean; url: string | null }> {
  const data = await fetchJSON('/api/tunnel/status');
  if (data?._error) return { active: false, url: null };
  return { active: !!data.active, url: data.url || null };
}

export async function getBaseUrl(): Promise<string> {
  const { active, url } = await getTunnelStatus();
  if (active && url) return url.replace(/\/+$/, '');
  return config.DASHBOARD_URL.replace(/\/+$/, '');
}

// ── Plans ─────────────────────────────────────────────────────────

export async function getPlans(): Promise<PlansResult> {
  const data = await fetchJSON('/api/plans');
  if (data?._error) return { error: data._error, plans: [] };
  return { plans: data.plans || [], count: data.count || 0 };
}

export async function getPlan(planId: string): Promise<any> {
  return fetchJSON(`/api/plans/${planId}`);
}

export async function refinePlan(params: {
  message: string;
  planContent?: string;
  planId?: string;
  chatHistory?: Array<{ role: string; content: string }>;
  workingDir?: string;
  assetContext?: PlanAsset[];
}): Promise<RefineResult> {
  return postJSON('/api/plans/refine', {
    message: params.message,
    plan_content: params.planContent || '',
    plan_id: params.planId || '',
    chat_history: params.chatHistory || [],
    working_dir: params.workingDir || '',
    asset_context: params.assetContext || [],
  });
}

export async function createPlan(params: {
  title: string;
  content: string;
  workingDir?: string;
}): Promise<CreateResult> {
  return postJSON('/api/plans/create', {
    path: params.workingDir || '.',
    title: params.title,
    content: params.content,
    working_dir: params.workingDir,
  });
}

export async function savePlan(planId: string, content: string): Promise<any> {
  return postJSON(`/api/plans/${planId}/save`, {
    content,
    change_source: 'bot',
  });
}

export async function getPlanAssets(planId: string): Promise<PlanAssetsResult> {
  const data = await fetchJSON(`/api/plans/${planId}/assets`);
  if (data?._error) return { error: data._error, assets: [] };
  return {
    plan_id: data.plan_id,
    assets: data.assets || [],
    count: data.count || 0,
  };
}

export async function uploadPlanAssets(
  planId: string,
  files: Array<{ name: string; contentType?: string; data: ArrayBuffer | Uint8Array }>
): Promise<PlanAssetsResult> {
  const form = new FormData();
  for (const file of files) {
    const bytes = file.data instanceof Uint8Array ? file.data : new Uint8Array(file.data);
    const arrayBuffer = new ArrayBuffer(bytes.byteLength);
    new Uint8Array(arrayBuffer).set(bytes);
    const blob = new Blob([arrayBuffer], { type: file.contentType || 'application/octet-stream' });
    form.append('files', blob, file.name);
  }

  const data = await fetchJSON(`/api/plans/${planId}/assets`, {
    method: 'POST',
    headers: getHeaders(null),
    body: form,
  });
  if (data?._error) return { error: data._error, assets: [] };
  return {
    plan_id: data.plan_id,
    assets: data.assets || [],
    count: data.count || 0,
  };
}

export async function launchPlan(planId: string, planContent: string): Promise<any> {
  return postJSON('/api/run', {
    plan: planContent,
    plan_id: planId,
  });
}

// ── Rooms ─────────────────────────────────────────────────────────

export async function getRooms(): Promise<RoomsResult> {
  const data = await fetchJSON('/api/rooms');
  if (data?._error) return { error: data._error, rooms: [], summary: {} };
  return { rooms: data.rooms || [], summary: data.summary || {} };
}

export async function getRoomChannel(roomId: string, limit = 1): Promise<any> {
  return fetchJSON(`/api/rooms/${roomId}/channel?limit=${limit}`);
}

// ── Stats & Search ────────────────────────────────────────────────

export async function getStats(): Promise<Stats> {
  return fetchJSON('/api/stats');
}

export async function getSkills(): Promise<Skill[]> {
  const data = await fetchJSON('/api/skills');
  if (data?._error) return [];
  return Array.isArray(data) ? data : [];
}

export async function semanticSearch(query: string, limit = 5): Promise<any> {
  return fetchJSON(`/api/search?q=${encodeURIComponent(query)}&limit=${limit}`);
}

export async function stopDashboard(): Promise<any> {
  return postJSON('/api/stop', {});
}

export async function shellCommand(command: string): Promise<any> {
  return postJSON('/api/shell', command);
}

export async function postComment(entityId: string, userId: string, body: string, parentId?: string): Promise<any> {
  return postJSON('/api/engagement/comments', {
    entity_id: entityId,
    user_id: userId,
    body,
    parent_id: parentId,
  });
}

export async function getEngagement(entityId: string): Promise<any> {
  return fetchJSON(`/api/engagement/${entityId}`);
}

// Default export as a mutable object for testability (sinon stubs)
const api = {
  getBaseUrl,
  getPlans,
  getPlan,
  refinePlan,
  createPlan,
  savePlan,
  getPlanAssets,
  uploadPlanAssets,
  launchPlan,
  getRooms,
  getRoomChannel,
  getStats,
  getSkills,
  semanticSearch,
  stopDashboard,
  shellCommand,
  postComment,
  getEngagement,
};

export default api;
