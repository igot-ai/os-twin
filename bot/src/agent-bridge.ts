/**
 * agent-bridge.ts — AI agent with tool-calling capabilities.
 *
 * Uses Gemini function calling to handle both Q&A about projects AND
 * proactive actions (create plans, list plans, check status, launch plans).
 *
 * Shared by Discord @mentions and Telegram free-text.
 */

import {
  GoogleGenerativeAI,
  SchemaType,
  type Content,
  type FunctionDeclaration,
  type FunctionCall,
} from '@google/generative-ai';
import config from './config';
import api, {
  type Plan,
  type Room,
  type PlanAsset,
  type PlansResult,
  type RoomsResult,
  type Stats,
  type ClawhubSkill,
  type RoomMessage,
} from './api';
import { getSession, setPlan, clearSession, getStagedImages, getStagedFiles, persistAfterMessage } from './sessions';
import { flushStagedAttachments } from './asset-staging';

/** Tool call arguments — maps tool name to expected args shape. */
interface ToolArgs {
  plan_id?: string;
  idea?: string;
  instruction?: string;
  room_id?: string;
  limit?: number;
  query?: string;
}

/** Memory note from the amem API. */
interface MemoryNote {
  title?: string;
  path?: string;
  tags?: string[];
  keywords?: string[];
  excerpt?: string;
  body?: string;
  links?: string[];
}

/** Staged file metadata. */
interface StagedFile {
  name: string;
  contentType?: string;
}

// ── Chat history helpers ──────────────────────────────────────────────────

/** Max prior turns (user+assistant pairs) to send to Gemini. */
const MAX_HISTORY_TURNS = 10;
const MAX_HISTORY_MESSAGES = MAX_HISTORY_TURNS * 2;

/** Hard cap on messages persisted to sessions.json per user. */
const MAX_PERSISTED_MESSAGES = 50;

/**
 * Sanitize chat history so it satisfies Gemini's constraints:
 * - roles must alternate (user, model, user, model, ...)
 * - must start with "user"
 * - consecutive same-role messages are merged
 */
function sanitizeHistory(messages: Array<{ role: string; content: string }>): Array<{ role: string; content: string }> {
  const result: Array<{ role: string; content: string }> = [];
  for (const msg of messages) {
    if (result.length > 0 && result[result.length - 1].role === msg.role) {
      result[result.length - 1].content += '\n\n' + msg.content;
    } else {
      result.push({ ...msg });
    }
  }
  // Gemini requires history to start with "user"
  while (result.length > 0 && result[0].role !== 'user') {
    result.shift();
  }
  return result;
}

/**
 * Convert session ChatMessage[] to Gemini Content[] format.
 * Maps role: 'assistant' → 'model' and wraps content in parts[].
 */
function toGeminiHistory(messages: Array<{ role: string; content: string }>): Content[] {
  return sanitizeHistory(messages).map((msg) => ({
    role: msg.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: msg.content }],
  }));
}
import { type ConnectorConfig, type AttachmentMeta } from './connectors/base';
import { registry } from './connectors/registry';

// ── Tool definitions for Gemini function calling ──────────────────────────

const toolDeclarations: FunctionDeclaration[] = [
  {
    name: 'list_plans',
    description: 'List all current plans in the Ostwin system with their status, completion %, and epic counts.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {},
    },
  },
  {
    name: 'get_plan_status',
    description: 'Get detailed status of a specific plan by its ID, including epics and war-room progress.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        plan_id: {
          type: SchemaType.STRING,
          description: 'The plan ID to look up (e.g. "my-blog-website")',
        },
      },
      required: ['plan_id'],
    },
  },
  {
    name: 'create_plan',
    description:
      'Create a new plan from a user idea. Use this when the user asks to build, make, create, or start a new project. ' +
      'This will draft a structured plan with epics and tasks using AI, then save it.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        idea: {
          type: SchemaType.STRING,
          description: 'Description of what the user wants to build (e.g. "interactive blog website with CMS")',
        },
      },
      required: ['idea'],
    },
  },
  {
    name: 'refine_plan',
    description:
      'Refine or modify an existing plan. Use this when the user wants to add features, change epics, ' +
      'update tasks, add acceptance criteria, or make any changes to a plan. ' +
      'Also use when the user says "add authentication", "break into more epics", "make it simpler", etc.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        plan_id: {
          type: SchemaType.STRING,
          description: 'The plan ID to refine (e.g. "gold-mining.plan")',
        },
        instruction: {
          type: SchemaType.STRING,
          description: 'What changes to make to the plan (e.g. "add JWT authentication to EPIC-002")',
        },
      },
      required: ['plan_id', 'instruction'],
    },
  },
  {
    name: 'launch_plan',
    description:
      'Launch an existing plan into war-rooms so agents start working on it. ' +
      'Use this when the user explicitly asks to run, start, launch, or execute a plan.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        plan_id: {
          type: SchemaType.STRING,
          description: 'The plan ID to launch',
        },
      },
      required: ['plan_id'],
    },
  },
  {
    name: 'get_war_room_status',
    description: 'Get the current status of all active war-rooms, including which epics are being worked on and their progress.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {},
    },
  },
  {
    name: 'resume_plan',
    description:
      'Resume a previously failed or stopped plan. Use this when the user asks to resume, retry, or re-run a plan that has failed.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        plan_id: {
          type: SchemaType.STRING,
          description: 'The plan ID to resume',
        },
      },
      required: ['plan_id'],
    },
  },
  {
    name: 'get_logs',
    description: 'Read the latest messages from a war-room channel. Useful for checking what agents are saying or debugging issues.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        room_id: {
          type: SchemaType.STRING,
          description: 'The war-room ID to read logs from (e.g. "room-001")',
        },
        limit: {
          type: SchemaType.NUMBER,
          description: 'Number of messages to retrieve (default 10)',
        },
      },
      required: ['room_id'],
    },
  },
  {
    name: 'get_health',
    description: 'Check the overall system health: manager status, bot status, and war-room summary.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {},
    },
  },
  {
    name: 'search_skills',
    description: 'Search the ClawHub marketplace for available AI skills that can be installed.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        query: {
          type: SchemaType.STRING,
          description: 'Search query (e.g. "web search", "code review", "testing")',
        },
      },
      required: ['query'],
    },
  },
  {
    name: 'get_plan_assets',
    description:
      'List all assets and artifacts produced by a plan. Use this when the user asks about files, ' +
      'artifacts, deliverables, outputs, or the product of a plan.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        plan_id: {
          type: SchemaType.STRING,
          description: 'The plan ID (e.g. "gold-mining.plan")',
        },
      },
      required: ['plan_id'],
    },
  },
  {
    name: 'get_memories',
    description:
      'List the memories (knowledge notes) saved during a plan\'s execution. Each memory captures ' +
      'architectural decisions, code patterns, lessons learned, and context discovered by agents. ' +
      'Use this when the user asks about memories, what agents learned, what was saved, or knowledge base.',
    parameters: {
      type: SchemaType.OBJECT,
      properties: {
        plan_id: {
          type: SchemaType.STRING,
          description: 'The plan ID (e.g. "gold-mining.plan")',
        },
      },
      required: ['plan_id'],
    },
  },
];

// ── Tool execution handlers ───────────────────────────────────────────────

interface AgentContext {
  userId: string;
  platform: string;
  referencedMessageContent?: string;
  /** Metadata about attached files so the agent knows assets were staged. */
  attachments?: AttachmentMeta[];
}

async function executeTool(
  call: FunctionCall,
  ctx: AgentContext,
  attachments: Array<{ buffer: Buffer; name: string }>,
): Promise<{ name: string; response: Record<string, unknown> }> {
  const { name, args } = call;

  switch (name) {
    case 'list_plans': {
      const data = await api.getPlans();
      return {
        name,
        response: {
          success: true,
          plans: data.plans.map((p: Plan) => ({
            plan_id: p.plan_id,
            title: p.title,
            status: p.status,
            pct_complete: p.pct_complete,
            epic_count: p.epic_count || 0,
          })),
          total: data.plans.length,
        },
      };
    }

    case 'get_plan_status': {
      const planId = (args as ToolArgs).plan_id || '';
      const [plan, epics, rooms] = await Promise.all([
        api.getPlan(planId) as Promise<Plan & { _error?: string }>,
        api.getPlanEpics(planId),
        api.getRooms(),
      ]);
      if (plan?._error) {
        return { name, response: { success: false, error: `Plan "${planId}" not found.` } };
      }
      const planRooms = rooms.rooms.filter((r: Room) =>
        (r as Room & { plan_id?: string }).plan_id === planId || r.epic_ref?.startsWith('EPIC-'),
      );
      return {
        name,
        response: {
          success: true,
          plan_id: planId,
          title: plan.title,
          status: plan.status,
          pct_complete: plan.pct_complete,
          epics: epics,
          active_rooms: planRooms.map((r: Room) => ({
            room_id: r.room_id,
            epic_ref: r.epic_ref,
            status: r.status,
          })),
        },
      };
    }

    case 'create_plan': {
      const idea = (args as ToolArgs).idea || '';
      const session = getSession(ctx.userId, ctx.platform);
      const workingDir =
        session.workingDir ||
        registry.getConfig(ctx.platform as 'discord' | 'telegram' | 'slack')?.settings?.working_dir ||
        '';

      // Get staged files (all types) and images (for vision API)
      const stagedImages = getStagedImages(ctx.userId, ctx.platform);
      const stagedFiles = getStagedFiles(ctx.userId, ctx.platform);
      const hasImages = stagedImages.length > 0;
      const hasFiles = stagedFiles.length > 0;
      
      console.log(`[AGENT] create_plan: hasImages=${hasImages}, hasFiles=${hasFiles}, stagedFiles=${stagedFiles.length}`);
      if (hasFiles) {
        console.log(`[AGENT] Staged files:`, stagedFiles.map((f: StagedFile) => ({ name: f.name, type: f.contentType })));
      }

      // Step 1: AI generates the plan content (include files/images if available)
      let refineMessage = `Draft a new plan for: ${idea}`;
      if (hasFiles) {
        const fileList = stagedFiles.map((f: StagedFile) => `- ${f.name} (${f.contentType})`).join('\n');
        refineMessage += `\n\nThe user has attached ${stagedFiles.length} file(s):\n${fileList}\n\nIMPORTANT INSTRUCTIONS FOR ASSETS:\n1. These files WILL BE SAVED as plan assets automatically after the plan is created.\n2. In each epic, explicitly reference these assets by filename.\n3. Describe HOW each asset should be used in that epic's implementation.\n4. For images: specify which UI components they belong to, their placement, and styling.\n5. For design mockups: break them down into sections and map each section to an epic.\n6. Create a dedicated "Assets" section in the plan listing all files and their intended use.`;
      }
      const result = await api.refinePlan({
        message: refineMessage,
        workingDir,
        images: stagedImages,
      });

      if (result?._error) {
        return { name, response: { success: false, error: result._error } };
      }

      const planText =
        result.plan || result.refined_plan || result.raw_result?.full_response || '';
      const planSlug = idea
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .slice(0, 60);

      // Step 2: Persist the plan
      const created = await api.createPlan({
        title: idea,
        content: planText,
        workingDir: workingDir || '.',
      });

      const finalPlanId = created?.plan_id || planSlug;

      // Step 3: Update session state so user can continue refining via @mention
      setPlan(ctx.userId, ctx.platform, finalPlanId);

      // Step 4: Save staged files to the plan (now that we have a planId)
      let savedAssets: Array<{ original_name: string }> = [];
      if (hasFiles) {
        const flushResult = await flushStagedAttachments(ctx.userId, ctx.platform, finalPlanId);
        savedAssets = flushResult.saved;
        if (flushResult.failures.length > 0) {
          console.warn(`[AGENT] Failed to save some staged files:`, flushResult.failures);
        }
        console.log(`[AGENT] Saved ${savedAssets.length} staged file(s) to plan ${finalPlanId}`);
      }

      return {
        name,
        response: {
          success: true,
          plan_id: finalPlanId,
          title: idea,
          plan_content: planText.length > 3000 ? planText.slice(0, 3000) + '\n...(truncated)' : planText,
          explanation: result.explanation || '',
          epic_count: (planText.match(/EPIC-\d+/g) || []).length,
          files_saved: savedAssets.length,
          images_used: hasImages ? stagedImages.length : 0,
          message:
            `Plan "${finalPlanId}" has been created and saved. ` +
            (savedAssets.length > 0 ? `I saved ${savedAssets.length} attached file(s) as plan assets. ` : '') +
            `The user is now in editing mode and can send further instructions to refine it, ` +
            `upload more assets, or use /cancel to exit editing.`,
        },
      };
    }

    case 'refine_plan': {
      const planId = (args as ToolArgs).plan_id || '';
      const instruction = (args as ToolArgs).instruction || '';
      const plan = await api.getPlan(planId) as Plan & { _error?: string };
      if (plan?._error) {
        return { name, response: { success: false, error: `Plan "${planId}" not found.` } };
      }
      const planContent = plan.content || '';

      // Get session for chat history context
      const session = getSession(ctx.userId, ctx.platform);
      const result = await api.refinePlan({
        message: instruction,
        planId,
        planContent,
        chatHistory: session.chatHistory.slice(-20),
        workingDir: session.workingDir,
      });
      if (result?._error) {
        return { name, response: { success: false, error: result._error } };
      }
      const refinedPlan = result.plan || result.refined_plan || '';
      if (refinedPlan) {
        await api.savePlan(planId, refinedPlan);
      }
      return {
        name,
        response: {
          success: true,
          plan_id: planId,
          explanation: result.explanation || 'Plan updated.',
          message: `Plan "${planId}" has been refined and saved.`,
        },
      };
    }

    case 'launch_plan': {
      const planId = (args as ToolArgs).plan_id || '';
      const plan = await api.getPlan(planId) as Plan & { _error?: string };
      if (plan?._error) {
        return { name, response: { success: false, error: `Plan "${planId}" not found.` } };
      }
      const content = plan.content || '';
      const result = await api.launchPlan(planId, content);
      if (result?._error) {
        return { name, response: { success: false, error: result._error } };
      }
      return {
        name,
        response: {
          success: true,
          plan_id: planId,
          message: `Plan "${planId}" has been launched. War-rooms are being created for each epic.`,
        },
      };
    }

    case 'get_war_room_status': {
      const [roomsData, stats] = await Promise.all([api.getRooms(), api.getStats()]);
      return {
        name,
        response: {
          success: true,
          rooms: roomsData.rooms.map((r: Room) => ({
            room_id: r.room_id,
            epic_ref: r.epic_ref,
            status: r.status,
            plan_id: (r as Room & { plan_id?: string }).plan_id,
          })),
          summary: roomsData.summary,
          stats: {
            total_plans: stats?.total_plans?.value ?? '?',
            active_epics: stats?.active_epics?.value ?? '?',
            completion_rate: stats?.completion_rate?.value ?? '?',
            escalations: stats?.escalations_pending?.value ?? 0,
          },
        },
      };
    }

    case 'resume_plan': {
      const planId = (args as ToolArgs).plan_id || '';
      const plan = await api.getPlan(planId) as Plan & { _error?: string };
      if (plan?._error) {
        return { name, response: { success: false, error: `Plan "${planId}" not found.` } };
      }
      const content = plan.content || '';
      const result = await api.resumePlan(planId, content);
      if (result?._error) {
        return { name, response: { success: false, error: result._error } };
      }
      return {
        name,
        response: {
          success: true,
          plan_id: planId,
          message: `Plan "${planId}" is being resumed. Existing war-rooms will continue from where they left off.`,
        },
      };
    }

    case 'get_logs': {
      const roomId = (args as ToolArgs).room_id || '';
      const limit = (args as ToolArgs).limit || 10;
      const data = await api.getRoomChannel(roomId, limit);
      if (data?._error) {
        return { name, response: { success: false, error: data._error } };
      }
      const msgs = data?.messages || data || [];
      return {
        name,
        response: {
          success: true,
          room_id: roomId,
          messages: Array.isArray(msgs)
             ? msgs.map((m: RoomMessage) => ({
                from: m.from,
                type: m.type,
                body: (m.body || '').slice(0, 300),
              }))
            : [],
          count: Array.isArray(msgs) ? msgs.length : 0,
        },
      };
    }

    case 'get_health': {
      const [managerStatus, botStatus, roomsData] = await Promise.all([
        api.getManagerStatus(),
        api.getBotStatus(),
        api.getRooms(),
      ]);
      return {
        name,
        response: {
          success: true,
          manager: {
            running: managerStatus?.running ?? false,
            pid: managerStatus?.pid,
          },
          bot: {
            running: botStatus?.running ?? false,
            pid: botStatus?.pid,
            available: botStatus?.available ?? false,
          },
          war_rooms: {
            total: roomsData.summary?.total || 0,
            passed: roomsData.summary?.passed || 0,
            failed: roomsData.summary?.failed_final || 0,
            active:
              (roomsData.summary?.total || 0) -
              (roomsData.summary?.passed || 0) -
              (roomsData.summary?.failed_final || 0),
          },
        },
      };
    }

    case 'search_skills': {
      const query = (args as ToolArgs).query || '';
      const results = await api.searchSkillsClawhub(query);
      return {
        name,
        response: {
          success: true,
          query,
          skills: results.slice(0, 10).map((s: ClawhubSkill) => ({
            slug: s.slug || s.name,
            description: s.description,
            author: s.author,
            downloads: s.downloads,
          })),
          total: results.length,
          message: results.length
            ? `Found ${results.length} skill(s). Install with: /skillinstall <slug>`
            : `No skills found for "${query}".`,
        },
      };
    }

    case 'get_plan_assets': {
      const planId = (args as ToolArgs).plan_id || '';
      const result = await api.getPlanAssets(planId);
      if (result?.error) {
        return { name, response: { success: false, error: result.error } };
      }
      return {
        name,
        response: {
          success: true,
          plan_id: planId,
          total: result.count || result.assets?.length || 0,
          assets: (result.assets || []).map((a: PlanAsset) => ({
            name: a.original_name || a.filename,
            path: a.path,
            type: a.asset_type || 'unknown',
            epic_ref: a.bound_epics?.[0] || null,
            size: a.size_bytes || null,
          })),
          message: result.assets?.length
            ? `Found ${result.assets.length} asset(s) for plan "${planId}".`
            : `No assets found for plan "${planId}".`,
        },
      };
    }

    case 'get_memories': {
      const planId = (args as ToolArgs).plan_id || '';
      try {
        const [notesRes, statsRes, treeRes, graphImage] = await Promise.all([
          api.fetchJSON(`/api/amem/${planId}/notes`),
          api.fetchJSON(`/api/amem/${planId}/stats`),
          api.fetchJSON(`/api/amem/${planId}/tree`),
          api.fetchBinary(`/api/amem/${planId}/graph-image`),
        ]);
        const notes = Array.isArray(notesRes) ? notesRes : [];

        // Attach graph image if available
        if (graphImage) {
          attachments.push({ buffer: graphImage, name: 'memory-graph.png' });
        }

        return {
          name,
          response: {
            success: true,
            plan_id: planId,
            total_notes: notes.length,
            has_graph_image: !!graphImage,
            directory_tree: treeRes?.tree || '(unavailable)',
            stats: {
              total_tags: statsRes?.total_tags || 0,
              total_keywords: statsRes?.total_keywords || 0,
              categories: statsRes?.categories || [],
            },
            memories: notes.slice(0, 15).map((n: MemoryNote) => ({
              title: n.title,
              path: n.path,
              tags: n.tags || [],
              keywords: n.keywords || [],
              excerpt: n.excerpt || n.body?.slice(0, 200) || '',
              links_count: n.links?.length || 0,
            })),
            message: notes.length
              ? `Found ${notes.length} memory note(s) for plan "${planId}". A graph visualization is attached.`
              : `No memories found for plan "${planId}".`,
          },
        };
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : String(err);
        return { name, response: { success: false, error: `Failed to fetch memories: ${message}` } };
      }
    }

    default:
      return { name, response: { error: `Unknown tool: ${name}` } };
  }
}

// ── Fast-path: skip Gemini for trivial messages ──────────────────────────

const TRIVIAL_PATTERNS = [
  /^(hi|hello|hey|yo|sup)[\s!.?]*$/i,
  /^(thanks|thank you|thx|ty|cheers)[\s!.?]*$/i,
  /^(ok|okay|k|got it|sure|yep|yeah|yes|no|nope|alright)[\s!.?]*$/i,
  /^(good|great|nice|cool|awesome|perfect|wow)[\s!.?]*$/i,
  /^(bye|goodbye|cya|see ya|later)[\s!.?]*$/i,
];

const TRIVIAL_RESPONSES: Record<string, string[]> = {
  greeting: ['Hey! How can I help with your project?', 'Hello! What would you like to do?'],
  thanks: ['You\'re welcome!', 'Glad to help!'],
  ack: ['Got it. Let me know if you need anything else.'],
  positive: ['Glad to hear it! Need anything else?'],
  bye: ['See you later! Your session is still active for 30 minutes.'],
};

function detectTrivial(text: string): string | null {
  const t = text.trim();
  if (t.length > 50) return null; // Long messages are never trivial
  if (TRIVIAL_PATTERNS[0].test(t)) return 'greeting';
  if (TRIVIAL_PATTERNS[1].test(t)) return 'thanks';
  if (TRIVIAL_PATTERNS[2].test(t)) return 'ack';
  if (TRIVIAL_PATTERNS[3].test(t)) return 'positive';
  if (TRIVIAL_PATTERNS[4].test(t)) return 'bye';
  return null;
}

// ── Context cache: avoid fetching plans/rooms on every message ───────────

interface CachedContext {
  plans: PlansResult;
  rooms: RoomsResult;
  fetchedAt: number;
}

const CONTEXT_CACHE_TTL_MS = 15_000; // 15 seconds
let _contextCache: CachedContext | null = null;

/** Invalidate the context cache. Exported for testing. */
export function invalidateContextCache(): void {
  _contextCache = null;
}

async function getContextCached(): Promise<{ plans: PlansResult; rooms: RoomsResult }> {
  if (_contextCache && Date.now() - _contextCache.fetchedAt < CONTEXT_CACHE_TTL_MS) {
    return { plans: _contextCache.plans, rooms: _contextCache.rooms };
  }
  const [plans, rooms] = await Promise.all([api.getPlans(), api.getRooms()]);
  _contextCache = { plans, rooms, fetchedAt: Date.now() };
  return { plans, rooms };
}

// ── Tool retry wrapper ───────────────────────────────────────────────────

/** Tools that perform side-effects and must NOT be retried on failure. */
const NON_IDEMPOTENT_TOOLS = new Set([
  'create_plan',
  'launch_plan',
  'resume_plan',
  'refine_plan',
]);

async function executeToolWithRetry(
  call: FunctionCall,
  ctx: AgentContext,
  attachments: Array<{ buffer: Buffer; name: string }>,
  timeoutMs: number,
): Promise<{ name: string; response: Record<string, unknown> }> {
  const withTimeout = <T>(p: Promise<T>, ms: number, label: string): Promise<T> =>
    Promise.race([
      p,
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error(`${label} timed out after ${ms / 1000}s`)), ms),
      ),
    ]);

  const canRetry = !NON_IDEMPOTENT_TOOLS.has(call.name);

  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      return await withTimeout(
        executeTool(call, ctx, attachments),
        timeoutMs,
        `tool:${call.name}`,
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      if (attempt === 0 && canRetry && !message.includes('timed out')) {
        console.warn(`[BRIDGE] Tool ${call.name} failed (attempt 1), retrying: ${message}`);
        continue;
      }
      return { name: call.name, response: { error: message } as Record<string, unknown> };
    }
  }
  return { name: call.name, response: { error: 'Unexpected retry exhaustion' } };
}

// ── Main agent entry point ────────────────────────────────────────────────

export interface AgentResponse {
  text: string;
  attachments?: Array<{ buffer: Buffer; name: string }>;
}

export async function askAgent(
  question: string,
  ctx?: AgentContext,
): Promise<AgentResponse> {
  const pendingAttachments: Array<{ buffer: Buffer; name: string }> = [];

  if (!config.GOOGLE_API_KEY) {
    return { text: '❌ `GOOGLE_API_KEY` is not set in the bot environment.' };
  }

  const agentCtx: AgentContext = ctx || { userId: 'unknown', platform: 'unknown' };
  const session = getSession(agentCtx.userId, agentCtx.platform);

  // ── Fast path: skip Gemini for trivial messages ──
  // Only short-circuit when there's no active plan session.  In multi-turn
  // workflows (drafting, editing), "yes"/"no"/"ok" are often confirmations
  // that need to reach Gemini so tool calls can proceed.
  const hasAttachments = agentCtx.attachments && agentCtx.attachments.length > 0;
  const hasActivePlan = session.activePlanId && session.activePlanId !== 'new';
  if (!hasAttachments && !hasActivePlan) {
    const trivialType = detectTrivial(question);
    if (trivialType) {
      const responses = TRIVIAL_RESPONSES[trivialType] || ['Got it.'];
      const reply = responses[Math.floor(Math.random() * responses.length)];
      session.chatHistory.push({ role: 'user', content: question });
      session.chatHistory.push({ role: 'assistant', content: reply });
      if (session.chatHistory.length > MAX_PERSISTED_MESSAGES) {
        session.chatHistory.splice(0, session.chatHistory.length - MAX_PERSISTED_MESSAGES);
      }
      persistAfterMessage();
      return { text: reply };
    }
  }

  // ── Load conversation history ──
  const recentHistory = session.chatHistory.slice(-MAX_HISTORY_MESSAGES);
  const geminiHistory = toGeminiHistory(recentHistory);

  // ── Build system prompt (lazy context — tools fetch details on demand) ──
  const referenceContext = agentCtx.referencedMessageContent
    ? `\n\n## Referenced Message\nThe user is replying to this message:\n"${agentCtx.referencedMessageContent}"`
    : '';

  const attachmentContext = agentCtx.attachments?.length
    ? `\n\n## Attached Files\nThe user has attached ${agentCtx.attachments.length} file(s) with this message:\n` +
      agentCtx.attachments.map(a => `- ${a.name} (${a.contentType || 'unknown type'})`).join('\n') +
      `\nThese files are staged and will be automatically linked to any plan you create.`
    : '';

  const activePlanContext = session.activePlanId
    ? `\n\n## Active Plan\nThe user is currently working on plan: **${session.activePlanId}**. When they say "the plan", "this plan", or "it", they mean this plan.`
    : '';

  // Fetch cached context — only a summary line, not full data dump
  const { plans: plansData, rooms: roomsData } = await getContextCached();
  const planCount = plansData.plans?.length || 0;
  const activeRooms = roomsData.rooms?.filter((r: Room) => !['passed', 'failed-final'].includes(r.status))?.length || 0;
  const contextSummary = `You have access to ${planCount} plan(s) and ${activeRooms} active war-room(s). Use list_plans or get_war_room_status tools to get details when needed.`;

  const systemPrompt = `You are OS Twin, an autonomous AI assistant that manages software projects through the Ostwin multi-agent war-room orchestrator.

You can ANSWER QUESTIONS and TAKE ACTIONS by calling tools. You have 12 tools available.

RULES:
- BUILD/CREATE something new → create_plan
- MODIFY/REFINE an existing plan → refine_plan
- STATUS/PROGRESS queries → list_plans or get_war_room_status
- LAUNCH/START a plan → launch_plan
- RESUME a failed plan → resume_plan
- LOGS/MESSAGES from agents → get_logs
- SYSTEM HEALTH → get_health
- FIND/SEARCH skills → search_skills
- ASSETS/ARTIFACTS/FILES → get_plan_assets
- MEMORIES/KNOWLEDGE → get_memories
- Be concise (1-3 paragraphs). Present tool results clearly.
- For status questions, ALWAYS use tools — don't guess from context.
- If user attached files + wants to build something → call create_plan.

## System Context
${contextSummary}${activePlanContext}${referenceContext}${attachmentContext}`;

  try {
    const genAI = new GoogleGenerativeAI(config.GOOGLE_API_KEY);
    const model = genAI.getGenerativeModel({
      model: config.GEMINI_MODEL,
      tools: [{ functionDeclarations: toolDeclarations }],
    });

    const chat = model.startChat({
      history: geminiHistory,
      systemInstruction: { role: 'system', parts: [{ text: systemPrompt }] },
    });

    // ── Gemini interaction with timeouts ──
    const AGENT_TIMEOUT_MS = 45_000;
    const TOOL_TIMEOUT_MS = 30_000;

    const withTimeout = <T>(p: Promise<T>, ms: number, label: string): Promise<T> =>
      Promise.race([
        p,
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error(`${label} timed out after ${ms / 1000}s`)), ms),
        ),
      ]);

    const agentStart = Date.now();

    let result = await withTimeout(chat.sendMessage(question), AGENT_TIMEOUT_MS, 'Gemini');
    let response = result.response;

    // Function-calling loop with timeout + retry
    const MAX_TOOL_ROUNDS = 5;
    let lastToolResults: Array<{ name: string; response: Record<string, unknown> }> = [];
    for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
      const elapsed = Date.now() - agentStart;
      if (elapsed > AGENT_TIMEOUT_MS) {
        console.warn(`[BRIDGE] Agent timeout after ${round} tool rounds (${elapsed}ms)`);
        break;
      }

      const calls = response.functionCalls();
      if (!calls || calls.length === 0) break;

      // Execute tools in parallel with retry on transient failures
      const toolResults = await Promise.all(
        calls.map((call) => executeToolWithRetry(call, agentCtx, pendingAttachments, TOOL_TIMEOUT_MS)),
      );
      lastToolResults = toolResults;

      // Send tool results back to Gemini
      const remainingMs = Math.max(5000, AGENT_TIMEOUT_MS - (Date.now() - agentStart));
      result = await withTimeout(
        chat.sendMessage(
          toolResults.map((r) => ({
            functionResponse: { name: r.name, response: r.response },
          })),
        ),
        remainingMs,
        'Gemini',
      );
      console.log('result', JSON.stringify(result, null, 2));
      response = result.response;
    }

    let answer = response.text?.();
    if (!answer && lastToolResults.length > 0) {
      const successResult = lastToolResults.find(r => r.response?.success && r.response?.message);
      if (successResult?.response?.message && typeof successResult.response.message === 'string') {
        answer = successResult.response.message;
      } else {
        const errorResult = lastToolResults.find(r => r.response?.error);
        if (errorResult?.response?.error) {
          answer = `⚠️ Tool ${errorResult.name} failed: ${errorResult.response.error}`;
        }
      }
    }
    if (!answer) return { text: '⚠️ AI returned an empty response.' };

    // Persist conversation turn
    session.chatHistory.push({ role: 'user', content: question });
    session.chatHistory.push({ role: 'assistant', content: answer });
    if (session.chatHistory.length > MAX_PERSISTED_MESSAGES) {
      session.chatHistory.splice(0, session.chatHistory.length - MAX_PERSISTED_MESSAGES);
    }
    persistAfterMessage();

    return {
      text: answer,
      attachments: pendingAttachments.length > 0 ? [...pendingAttachments] : undefined,
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error('[BRIDGE] AI API error:', message);
    return { text: '⚠️ Failed to get a response from the AI model.' };
  }
}
