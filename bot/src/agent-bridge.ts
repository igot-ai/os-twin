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
  type FunctionDeclaration,
  type FunctionCall,
} from '@google/generative-ai';
import config from './config';
import api from './api';
import { getSession, setMode, setPlan, clearSession } from './sessions';
import { type ConnectorConfig } from './connectors/base';
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
];

// ── Tool execution handlers ───────────────────────────────────────────────

interface AgentContext {
  userId: string;
  platform: string;
}

async function executeTool(
  call: FunctionCall,
  ctx: AgentContext,
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

      // Step 1: AI generates the plan content
      const result = await api.refinePlan({
        message: `Draft a new plan for: ${idea}`,
        workingDir,
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

      return {
        name,
        response: {
          success: true,
          plan_id: finalPlanId,
          title: idea,
          plan_content: planText.length > 3000 ? planText.slice(0, 3000) + '\n...(truncated)' : planText,
          explanation: result.explanation || '',
          epic_count: (planText.match(/EPIC-\d+/g) || []).length,
          message:
            `Plan "${finalPlanId}" has been created and saved. ` +
            `The user is now in editing mode and can send further instructions to refine it, ` +
            `upload assets, or use /cancel to exit editing.`,
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

    default:
      return { name, response: { error: `Unknown tool: ${name}` } };
  }
}

// ── Main agent entry point ────────────────────────────────────────────────

export async function askAgent(
  question: string,
  ctx?: AgentContext,
): Promise<string> {
  if (!config.GOOGLE_API_KEY) {
    return '❌ `GOOGLE_API_KEY` is not set in the bot environment.';
  }

  // Default context for backward compat
  const agentCtx: AgentContext = ctx || { userId: 'unknown', platform: 'unknown' };

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

  const systemPrompt = `You are OS Twin, an autonomous AI assistant that manages software projects through the Ostwin multi-agent war-room orchestrator.

You have TWO capabilities:
1. **Answer questions** about existing projects, plans, war-rooms, and agent status.
2. **Take actions** by calling the available tools: create plans, list plans, check status, and launch plans.

IMPORTANT RULES:
- When the user asks to BUILD, MAKE, CREATE, or DEVELOP something → call create_plan with their idea.
- When the user asks about STATUS, PROGRESS, or WHAT'S RUNNING → call list_plans or get_war_room_status.
- When the user asks to LAUNCH, RUN, START, or EXECUTE a plan → call launch_plan.
- When answering questions, be concise (1-3 paragraphs for chat).
- Always present tool results in a user-friendly format with relevant details.
- After creating a plan, mention that the user can now send further instructions to refine it, upload assets, or run /cancel.

## Current Plans
${plansText}

## Active War-Rooms
${roomsText}`;

  try {
    const genAI = new GoogleGenerativeAI(config.GOOGLE_API_KEY);
    const model = genAI.getGenerativeModel({
      model: config.GEMINI_MODEL,
      tools: [{ functionDeclarations: toolDeclarations }],
    });

    // Start a chat with system instruction
    const chat = model.startChat({
      history: [],
      systemInstruction: { role: 'system', parts: [{ text: systemPrompt }] },
    });

    // First turn: send user's question
    let result = await chat.sendMessage(question);
    let response = result.response;

    // Function-calling loop: execute tools until the model produces a text response
    const MAX_TOOL_ROUNDS = 5;
    for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
      const calls = response.functionCalls();
      if (!calls || calls.length === 0) break;

      // Execute all tool calls in parallel
      const toolResults = await Promise.all(
        calls.map((call) => executeTool(call, agentCtx)),
      );

      // Send function responses back to the model
      result = await chat.sendMessage(
        toolResults.map((r) => ({
          functionResponse: { name: r.name, response: r.response },
        })),
      );
      response = result.response;
    }

    const answer = response.text?.();
    if (!answer) return '⚠️ AI returned an empty response.';

    return answer.length > 1900
      ? answer.slice(0, 1900) + '\n\n*…(truncated)*'
      : answer;
  } catch (err: any) {
    console.error('[BRIDGE] AI API error:', err.message);
    return '⚠️ Failed to get a response from the AI model.';
  }
}
