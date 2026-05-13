"""
OpenCode-backed chat endpoint for connectors.

Flow:
  1. Connector sends POST /api/chat with user message + conversation_id
  2. Backend gets/creates an OpenCode session for that conversation
  3. Sends user message to the session (with os-twin tool descriptions)
  4. AI responds — may include ```tool``` blocks for os-twin tools
  5. Backend parses tool calls, executes them via the dashboard REST API
  6. Sends tool results back to the SAME session as a follow-up message
  7. AI generates final response using the tool results
  8. Everything lives in the OpenCode session → full memory on next turn

Memory:
  - OpenCode session is the single source of truth
  - Slash command context injected via pendingContext (see agent-bridge.ts)
  - referencedMessageContent passed through for Discord reply context
  - Structured actions returned so connector can update session state
"""

from __future__ import annotations

import json
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dashboard.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

SYSTEM_PROMPT = """\
You are OS Twin, an autonomous AI assistant that manages software projects \
through the Ostwin multi-agent war-room orchestrator.

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
"""

TOOL_DESCRIPTIONS = """
## Available Tools

You have these tools. To call a tool, respond with a JSON block like:
```tool
{"name": "tool_name", "arguments": {"arg1": "value1"}}
```

### list_plans
List all current plans with status and completion %.
No arguments.

### get_plan_status
Get detailed status of a specific plan.
Arguments: plan_id (string, required)

### create_plan
Create a new plan from an idea.
Arguments: idea (string, required)

### refine_plan
Refine or modify an existing plan.
Arguments: plan_id (string, required), instruction (string, required)

### launch_plan
Launch a plan into war-rooms.
Arguments: plan_id (string, required)

### resume_plan
Resume a failed/stopped plan.
Arguments: plan_id (string, required)

### get_war_room_status
Get status of all active war-rooms.
No arguments.

### get_logs
Read latest messages from a war-room channel.
Arguments: plan_id (string, required), room_id (string, required), limit (number, optional, default 10)

### get_health
Check overall system health.
No arguments.

### search_skills
Search ClawHub marketplace for skills.
Arguments: query (string, required)

### get_plan_assets
List assets/artifacts for a plan.
Arguments: plan_id (string, required)

### get_memories
List memories/knowledge notes for a plan.
Arguments: plan_id (string, required)
"""


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    user_id: str = "unknown"
    platform: str = "unknown"
    working_dir: str | None = None
    attachments: list[dict] | None = None
    referenced_message_content: str | None = None


class ToolAction(BaseModel):
    type: str
    plan_id: str | None = None
    room_id: str | None = None


class ChatResponse(BaseModel):
    text: str
    conversation_id: str
    actions: list[ToolAction] | None = None


# ── Internal API helpers ──────────────────────────────────────────────────


def _get_internal_api_base() -> str:
    port = os.environ.get("DASHBOARD_PORT", "3366")
    return f"http://127.0.0.1:{port}"


def _get_internal_headers() -> dict:
    api_key = os.environ.get("OSTWIN_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


async def _api_get(path: str, params: dict | None = None) -> dict:
    base = _get_internal_api_base()
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base}{path}", params=params, headers=_get_internal_headers())
        if r.status_code >= 400:
            return {"error": f"API {r.status_code}: {r.text[:200]}"}
        return r.json()


async def _api_post(path: str, body: dict | None = None) -> dict:
    base = _get_internal_api_base()
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{base}{path}", json=body or {}, headers=_get_internal_headers())
        if r.status_code >= 400:
            return {"error": f"API {r.status_code}: {r.text[:200]}"}
        return r.json()


# ── Tool handlers ─────────────────────────────────────────────────────────

TOOL_HANDLERS = {}


def _tool(name):
    def decorator(fn):
        TOOL_HANDLERS[name] = fn
        return fn
    return decorator


@_tool("list_plans")
async def _list_plans(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    data = await _api_get("/api/plans")
    if "error" in data:
        return data, []
    plans = data.get("plans", [])
    return {
        "plans": [
            {"plan_id": p.get("plan_id"), "title": p.get("title"), "status": p.get("status")}
            for p in plans
        ],
        "count": data.get("count", len(plans)),
    }, []


@_tool("get_plan_status")
async def _get_plan_status(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "plan_id is required"}, []
    data = await _api_get(f"/api/plans/{plan_id}")
    if "error" in data:
        return data, []
    plan = data.get("plan", {})
    epics = data.get("epics", [])
    return {
        "plan_id": plan_id,
        "title": plan.get("title"),
        "status": plan.get("status"),
        "epic_count": len(epics),
        "epics": [
            {"epic_ref": e.get("epic_ref"), "title": e.get("title"), "status": e.get("status")}
            for e in epics
        ],
    }, []


@_tool("create_plan")
async def _create_plan(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    idea = args.get("idea", "")
    if not idea:
        return {"error": "idea is required"}, []
    data = await _api_post("/api/plans/create", {
        "title": idea,
        "content": "",
        "working_dir": ctx.get("working_dir"),
    })
    if "error" in data:
        return data, []
    plan_id = data.get("plan_id", "")
    if idea and plan_id:
        refine = await _api_post("/api/plans/refine", {
            "plan_id": plan_id,
            "message": f"Draft a new plan for: {idea}",
        })
        plan_text = refine.get("plan", refine.get("full_response", ""))
        if plan_text and plan_id:
            await _api_post(f"/api/plans/{plan_id}/save", {
                "content": plan_text,
                "change_source": "ai_create",
            })
    return {"plan_id": plan_id, "title": idea, "status": "created"}, [
        ToolAction(type="plan_created", plan_id=plan_id)
    ]


@_tool("refine_plan")
async def _refine_plan(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    plan_id = args.get("plan_id", "")
    instruction = args.get("instruction", "")
    if not plan_id:
        return {"error": "plan_id is required"}, []
    if not instruction:
        return {"error": "instruction is required"}, []
    data = await _api_post("/api/plans/refine", {
        "plan_id": plan_id,
        "message": instruction,
    })
    if "error" in data:
        return data, []
    refined = data.get("plan", data.get("full_response", ""))
    if refined and plan_id:
        await _api_post(f"/api/plans/{plan_id}/save", {
            "content": refined,
            "change_source": "ai_refine",
        })
    return {"plan_id": plan_id, "status": "refined", "explanation": data.get("explanation", "")}, []


@_tool("launch_plan")
async def _launch_plan(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "plan_id is required"}, []
    plan_data = await _api_get(f"/api/plans/{plan_id}")
    if "error" in plan_data:
        return plan_data, []
    plan_content = plan_data.get("plan", {}).get("content", "")
    if not plan_content:
        return {"error": f"Plan '{plan_id}' has no content"}, []
    result = await _api_post("/api/run", {
        "plan_id": plan_id,
        "plan": plan_content,
    })
    if "error" in result:
        return result, []
    return {"plan_id": plan_id, "status": "launched", "rooms": result.get("rooms", [])}, [
        ToolAction(type="plan_launched", plan_id=plan_id)
    ]


@_tool("resume_plan")
async def _resume_plan(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "plan_id is required"}, []
    result = await _api_post(f"/api/plans/{plan_id}/status", {"status": "running"})
    if "error" in result:
        return result, []
    return {"plan_id": plan_id, "status": "resuming"}, [
        ToolAction(type="plan_resumed", plan_id=plan_id)
    ]


@_tool("get_war_room_status")
async def _get_war_room_status(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    data = await _api_get("/api/stats")
    if "error" in data:
        return data, []
    return data, []


@_tool("get_logs")
async def _get_logs(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    plan_id = args.get("plan_id", "")
    room_id = args.get("room_id", "")
    limit = args.get("limit", 10)
    if not plan_id:
        return {"error": "plan_id is required"}, []
    if not room_id:
        return {"error": "room_id is required"}, []
    data = await _api_get(f"/api/plans/{plan_id}/rooms/{room_id}/channel")
    if "error" in data:
        return data, []
    return {"room_id": room_id, "messages": data.get("messages", data)}, []


@_tool("get_health")
async def _get_health(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    data = await _api_get("/api/status")
    return {"status": "healthy" if not data.get("error") else "unhealthy", "service": "os-twin-dashboard", "manager": data}, []


@_tool("search_skills")
async def _search_skills(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    query = args.get("query", "")
    if not query:
        return {"error": "query is required"}, []
    data = await _api_get("/api/skills/search", {"q": query})
    if "error" in data:
        return data, []
    skills = data if isinstance(data, list) else []
    return {"skills": skills[:10], "total": len(skills)}, []


@_tool("get_plan_assets")
async def _get_plan_assets(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "plan_id is required"}, []
    data = await _api_get(f"/api/plans/{plan_id}/assets")
    if "error" in data:
        return data, []
    return {"plan_id": plan_id, "assets": data.get("assets", [])}, []


@_tool("get_memories")
async def _get_memories(args: dict, ctx: dict) -> tuple[dict, list[ToolAction]]:
    plan_id = args.get("plan_id", "")
    if not plan_id:
        return {"error": "plan_id is required"}, []
    return {"plan_id": plan_id, "memories": []}, []


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, user: dict = Depends(get_current_user)):
    from dashboard.master_agent import (
        _opencode_chat,
        _session_registry,
        parse_custom_tool_calls,
        strip_tool_blocks,
    )

    conv_id = request.conversation_id or f"{request.platform}:{request.user_id}"
    session_id = await _session_registry.get_or_create(conv_id)

    user_text = request.message
    if request.referenced_message_content:
        user_text = f'[User is replying to: "{request.referenced_message_content}"]\n\n{user_text}'
    if request.attachments:
        file_list = "\n".join(
            f"  - {a.get('name', 'file')} ({a.get('contentType', 'unknown')})"
            for a in request.attachments
        )
        user_text += f"\n\nAttached files:\n{file_list}"

    try:
        raw_text = await _opencode_chat(
            session_id,
            [{"type": "text", "text": user_text}],
            system=SYSTEM_PROMPT + TOOL_DESCRIPTIONS,
            conversation_id=conv_id,
        )
    except Exception as e:
        logger.error("[CHAT] OpenCode chat failed: %s", e)
        raise HTTPException(status_code=502, detail=f"OpenCode error: {e}")

    tool_calls = parse_custom_tool_calls(raw_text)
    all_actions: list[ToolAction] = []

    max_rounds = 5
    for _ in range(max_rounds):
        if not tool_calls:
            break

        tool_results_text = ""
        for tc in tool_calls:
            handler = TOOL_HANDLERS.get(tc.name)
            if handler:
                try:
                    result, actions = await handler(tc.arguments, {
                        "user_id": request.user_id,
                        "platform": request.platform,
                        "working_dir": request.working_dir,
                    })
                    tool_results_text += f"\n[Tool: {tc.name}] Result: {json.dumps(result, default=str)}\n"
                    all_actions.extend(actions)
                except Exception as e:
                    tool_results_text += f"\n[Tool: {tc.name}] Error: {e}\n"
            else:
                tool_results_text += f"\n[Tool: {tc.name}] Unknown tool.\n"

        try:
            raw_text = await _opencode_chat(
                session_id,
                [{"type": "text", "text": tool_results_text}],
                conversation_id=conv_id,
            )
        except Exception as e:
            logger.error("[CHAT] OpenCode follow-up failed: %s", e)
            break

        tool_calls = parse_custom_tool_calls(raw_text)

    clean_text = strip_tool_blocks(raw_text)

    return ChatResponse(
        text=clean_text or "No response from AI.",
        conversation_id=conv_id,
        actions=all_actions or None,
    )


@router.delete("/api/chat/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    from dashboard.master_agent import end_conversation

    await end_conversation(conversation_id)
    return {"status": "deleted", "conversation_id": conversation_id}
