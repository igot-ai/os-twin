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
import api from './api';
import { getSession, setMode, setPlan, clearSession, getStagedImages, getStagedFiles, persistAfterMessage } from './sessions';
import { flushStagedAttachments } from './asset-staging';

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
          plans: data.plans.map((p: any) => ({
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
      const planId = (args as any).plan_id;
      const [plan, epics, rooms] = await Promise.all([
        api.getPlan(planId),
        api.getPlanEpics(planId),
        api.getRooms(),
      ]);
      if ((plan as any)?._error) {
        return { name, response: { success: false, error: `Plan "${planId}" not found.` } };
      }
      const planRooms = rooms.rooms.filter((r: any) =>
        r.plan_id === planId || r.epic_ref?.startsWith('EPIC-'),
      );
      return {
        name,
        response: {
          success: true,
          plan_id: planId,
          title: (plan as any).title,
          status: (plan as any).status,
          pct_complete: (plan as any).pct_complete,
          epics: epics,
          active_rooms: planRooms.map((r: any) => ({
            room_id: r.room_id,
            epic_ref: r.epic_ref,
            status: r.status,
          })),
        },
      };
    }

    case 'create_plan': {
      const idea = (args as any).idea;
      const session = getSession(ctx.userId, ctx.platform);
      const workingDir =
        session.workingDir ||
        registry.getConfig(ctx.platform as any)?.settings?.working_dir ||
        '';

      // Get staged files (all types) and images (for vision API)
      const stagedImages = getStagedImages(ctx.userId, ctx.platform);
      const stagedFiles = getStagedFiles(ctx.userId, ctx.platform);
      const hasImages = stagedImages.length > 0;
      const hasFiles = stagedFiles.length > 0;
      
      console.log(`[AGENT] create_plan: hasImages=${hasImages}, hasFiles=${hasFiles}, stagedFiles=${stagedFiles.length}`);
      if (hasFiles) {
        console.log(`[AGENT] Staged files:`, stagedFiles.map((f: any) => ({ name: f.name, type: f.contentType })));
      }

      // Step 1: AI generates the plan content (include files/images if available)
      let refineMessage = `Draft a new plan for: ${idea}`;
      if (hasFiles) {
        const fileList = stagedFiles.map((f: any) => `- ${f.name} (${f.contentType})`).join('\n');
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

      // Step 3: Update session state so user can continue editing
      setMode(ctx.userId, ctx.platform, 'editing');
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
      const planId = (args as any).plan_id;
      const instruction = (args as any).instruction;
      const plan = await api.getPlan(planId);
      if ((plan as any)?._error) {
        return { name, response: { success: false, error: `Plan "${planId}" not found.` } };
      }
      const planContent = (plan as any).content || '';

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
      const planId = (args as any).plan_id;
      const plan = await api.getPlan(planId);
      if ((plan as any)?._error) {
        return { name, response: { success: false, error: `Plan "${planId}" not found.` } };
      }
      const content = (plan as any).content || '';
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
          rooms: roomsData.rooms.map((r: any) => ({
            room_id: r.room_id,
            epic_ref: r.epic_ref,
            status: r.status,
            plan_id: r.plan_id,
          })),
          summary: roomsData.summary,
          stats: {
            total_plans: (stats as any)?.total_plans?.value ?? '?',
            active_epics: (stats as any)?.active_epics?.value ?? '?',
            completion_rate: (stats as any)?.completion_rate?.value ?? '?',
            escalations: (stats as any)?.escalations_pending?.value ?? 0,
          },
        },
      };
    }

    case 'resume_plan': {
      const planId = (args as any).plan_id;
      const plan = await api.getPlan(planId);
      if ((plan as any)?._error) {
        return { name, response: { success: false, error: `Plan "${planId}" not found.` } };
      }
      const content = (plan as any).content || '';
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
      const roomId = (args as any).room_id;
      const limit = (args as any).limit || 10;
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
            ? msgs.map((m: any) => ({
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
      const query = (args as any).query;
      const results = await api.searchSkillsClawhub(query);
      return {
        name,
        response: {
          success: true,
          query,
          skills: results.slice(0, 10).map((s: any) => ({
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
      const planId = (args as any).plan_id;
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
          assets: (result.assets || []).map((a: any) => ({
            name: a.name || a.filename,
            path: a.path || a.relative_path,
            type: a.asset_type || a.type || 'unknown',
            epic_ref: a.epic_ref || null,
            size: a.size_bytes || a.size || null,
          })),
          message: result.assets?.length
            ? `Found ${result.assets.length} asset(s) for plan "${planId}".`
            : `No assets found for plan "${planId}".`,
        },
      };
    }

    case 'get_memories': {
      const planId = (args as any).plan_id;
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
            memories: notes.slice(0, 15).map((n: any) => ({
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
      } catch (err: any) {
        return { name, response: { success: false, error: `Failed to fetch memories: ${err.message}` } };
      }
    }

    default:
      return { name, response: { error: `Unknown tool: ${name}` } };
  }
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

  // Default context for backward compat
  const agentCtx: AgentContext = ctx || { userId: 'unknown', platform: 'unknown' };

  // Load conversation history from session
  const session = getSession(agentCtx.userId, agentCtx.platform);
  const recentHistory = session.chatHistory.slice(-MAX_HISTORY_MESSAGES);
  const geminiHistory = toGeminiHistory(recentHistory);

  // Gather lightweight context in parallel
  const [plansData, roomsData] = await Promise.all([
    api.getPlans(),
    api.getRooms(),
  ]);

  const plansText = plansData.plans.length
    ? plansData.plans
        .map((p: any) => {
          const pct = p.pct_complete != null ? `${p.pct_complete}%` : p.status;
          return `- **${p.title}** (${p.plan_id}) — ${pct}, ${p.epic_count || 0} epics`;
        })
        .join('\n')
    : 'No plans found.';

  const roomsText = roomsData.rooms.length
    ? roomsData.rooms
        .map((r: any) => `- ${r.room_id}: ${r.epic_ref || 'N/A'} — status: ${r.status}`)
        .join('\n')
    : 'No active war-rooms.';

  // Build referenced message context if provided
  const referenceContext = agentCtx.referencedMessageContent
    ? `\n\n## Referenced Message\nThe user is replying to this message:\n"${agentCtx.referencedMessageContent}"`
    : '';

  // Build attachment context so the AI knows files were sent
  const attachmentContext = agentCtx.attachments?.length
    ? `\n\n## Attached Files\nThe user has attached ${agentCtx.attachments.length} file(s) with this message:\n` +
      agentCtx.attachments.map(a => `- ${a.name} (${a.contentType || 'unknown type'})`).join('\n') +
      `\nThese files are staged and will be automatically linked to any plan you create. If the user is asking to build something, call create_plan — the staged files will be used as reference material.`
    : '';

  const activePlanContext = session.activePlanId
    ? `\n\n## Active Plan\nThe user is currently working on plan: **${session.activePlanId}**. When they say "the plan", "this plan", or "it", they mean this plan.`
    : '';

  const systemPrompt = `You are OS Twin, an autonomous AI assistant that manages software projects through the Ostwin multi-agent war-room orchestrator.

You have TWO capabilities:
1. **Answer questions** about existing projects, plans, war-rooms, and agent status.
2. **Take actions** by calling the available tools.

Available tools: create plans, refine plans, list plans, check status, launch plans, resume failed plans, read war-room logs, check system health, search for skills, view plan assets/artifacts, and view agent memories.

IMPORTANT RULES:
- When the user asks to BUILD, MAKE, CREATE, or DEVELOP something NEW → call create_plan with their idea.
- When the user asks to ADD, CHANGE, UPDATE, MODIFY, or REFINE an existing plan → call refine_plan with the plan_id and instruction.
- When the user asks about STATUS, PROGRESS, or WHAT'S RUNNING → call list_plans or get_war_room_status.
- When the user asks to LAUNCH, RUN, START, or EXECUTE a plan → call launch_plan.
- When the user asks to RESUME, RETRY, or RE-RUN a failed plan → call resume_plan.
- When the user asks about LOGS, MESSAGES, or what agents are SAYING → call get_logs.
- When the user asks about HEALTH, SYSTEM STATUS, or if things are RUNNING → call get_health.
- When the user asks to FIND, SEARCH, or DISCOVER skills → call search_skills.
- When the user asks about ASSETS, ARTIFACTS, FILES, OUTPUTS, or DELIVERABLES of a plan → call get_plan_assets.
- When the user asks about MEMORIES, what agents LEARNED, KNOWLEDGE, or NOTES saved → call get_memories.
- When answering questions, be concise (1-3 paragraphs for chat).
- Always present tool results in a user-friendly format with relevant details.
- If the user has attached files and is asking to build something, ALWAYS call create_plan — the files will be incorporated automatically.
- NEVER treat a status question as a plan refinement instruction. If unsure, ask the user to clarify.

## Current Plans
${plansText}

## Active War-Rooms
${roomsText}${activePlanContext}${referenceContext}${attachmentContext}`;

  try {
    const genAI = new GoogleGenerativeAI(config.GOOGLE_API_KEY);
    const model = genAI.getGenerativeModel({
      model: config.GEMINI_MODEL,
      tools: [{ functionDeclarations: toolDeclarations }],
    });

    // Start a chat with conversation history and system instruction
    const chat = model.startChat({
      history: geminiHistory,
      systemInstruction: { role: 'system', parts: [{ text: systemPrompt }] },
    });

    // Wrap the entire Gemini interaction in a timeout
    const AGENT_TIMEOUT_MS = 25_000;
    const TOOL_TIMEOUT_MS = 10_000;

    const withTimeout = <T>(promise: Promise<T>, ms: number, label: string): Promise<T> =>
      Promise.race([
        promise,
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error(`${label} timed out after ${ms / 1000}s`)), ms),
        ),
      ]);

    const agentStart = Date.now();

    // First turn: send user's question
    let result = await withTimeout(chat.sendMessage(question), AGENT_TIMEOUT_MS, 'Gemini');
    let response = result.response;

    // Function-calling loop: execute tools until the model produces a text response
    const MAX_TOOL_ROUNDS = 5;
    for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
      if (Date.now() - agentStart > AGENT_TIMEOUT_MS) {
        console.warn(`[BRIDGE] Agent timeout after ${round} tool rounds`);
        break;
      }

      const calls = response.functionCalls();
      if (!calls || calls.length === 0) break;

      // Execute all tool calls in parallel with per-tool timeout
      const toolResults = await Promise.all(
        calls.map((call) =>
          withTimeout(
            executeTool(call, agentCtx, pendingAttachments),
            TOOL_TIMEOUT_MS,
            `tool:${call.name}`,
          ).catch((err) => ({
            name: call.name,
            response: { error: err.message } as Record<string, unknown>,
          })),
        ),
      );

      // Send function responses back to the model
      result = await withTimeout(
        chat.sendMessage(
          toolResults.map((r) => ({
            functionResponse: { name: r.name, response: r.response },
          })),
        ),
        AGENT_TIMEOUT_MS - (Date.now() - agentStart),
        'Gemini',
      );
      response = result.response;
    }

    const answer = response.text?.();
    if (!answer) return { text: '⚠️ AI returned an empty response.' };

    // Persist conversation turn (full answer, not truncated)
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
  } catch (err: any) {
    console.error('[BRIDGE] AI API error:', err.message);
    return { text: '⚠️ Failed to get a response from the AI model.' };
  }
}
