import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from dashboard.api_utils import (
    PLANS_DIR, WARROOMS_DIR, AGENTS_DIR,
    read_room, read_channel, find_room_dir
)
import dashboard.global_state as global_state

logger = logging.getLogger(__name__)

async def get_plans_context() -> str:
    """Gather context about all current plans."""
    from dashboard.routes.plans import list_plans
    try:
        # Mock user for list_plans which depends on it
        data = await list_plans(user={"username": "system"})
        plans = data.get("plans", [])
        if not plans:
            return "No plans found."
        
        lines = []
        for p in plans:
            pct = p.get("pct_complete", "N/A")
            if isinstance(pct, (int, float)):
                pct = f"{pct}%"
            lines.append(f"- **{p.get('title', 'Untitled')}** ({p.get('plan_id', 'unknown')}) — {pct}, {p.get('epic_count', 0)} epics")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error gathering plans context: {e}")
        return f"Plans context unavailable: {e}"

async def get_rooms_context() -> str:
    """Gather context about all active war-rooms."""
    from dashboard.routes.rooms import list_rooms
    try:
        data = await list_rooms(user={"username": "system"})
        rooms = data.get("rooms", [])
        if not rooms:
            return "No active war-rooms."
        
        lines = []
        for r in rooms:
            lines.append(f"- {r.get('room_id')}: {r.get('epic_ref', 'N/A')} — status: {r.get('status', 'unknown')}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error gathering rooms context: {e}")
        return f"Rooms context unavailable: {e}"

async def get_stats_context() -> str:
    """Gather aggregate project stats."""
    from dashboard.routes.plans import get_stats
    try:
        data = await get_stats(user={"username": "system"})
        if not data:
            return "Stats unavailable."
        
        # Format similar to JS bridge: Plans: 2 | Active epics: 5 | Completion: 45% | Escalations: 0
        stats = [
            f"Plans: {data.get('total_plans', {}).get('value', '?')}",
            f"Active epics: {data.get('active_epics', {}).get('value', '?')}",
            f"Completion: {data.get('completion_rate', {}).get('value', '?')}%",
            f"Escalations: {data.get('escalations_pending', {}).get('value', 0)}",
        ]
        return " | ".join(stats)
    except Exception as e:
        logger.error(f"Error gathering stats context: {e}")
        return f"Stats context unavailable: {e}"

async def search_memory_context(query: str) -> str:
    """Search shared memory for relevant messages/decisions."""
    from dashboard.routes.memory import search_memory
    try:
        data = await search_memory(text=query, user={"username": "system"})
        results = data.get("results", [])
        if not results:
            return "No relevant messages found."
        
        lines = []
        for r in results[:5]:  # Limit to 5 results like JS bridge
            room = r.get("room_id", "global")
            sender = r.get("from", "?")
            msg_type = r.get("type", "?")
            body = (r.get("body") or "").replace("\n", " ")[:200]
            lines.append(f"[{room}] {sender} → {msg_type}: {body}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error searching memory: {e}")
        return f"Search context unavailable: {e}"

async def ask_agent(question: str, platform: str = "generic") -> str:
    """
    Ask the Ostwin AI Agent a question about the project.
    
    1. Gather context from plans, rooms, stats, and memory.
    2. Build a system prompt.
    3. Call the configured AI provider.
    4. Format and return the answer.
    """
    # 1. Gather context in parallel
    plans, rooms, stats, search = await asyncio.gather(
        get_plans_context(),
        get_rooms_context(),
        get_stats_context(),
        search_memory_context(question)
    )
    
    # 2. Check for API keys and select provider
    # Prefer keys from environment or .env file
    gemini_key = os.environ.get("GOOGLE_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    
    # Fallback to checking .ostwin/.env if not in environment
    if not any([gemini_key, anthropic_key, openai_key]):
        env_file = Path.home() / ".ostwin" / ".env"
        if env_file.exists():
            from dotenv import dotenv_values
            env_vals = dotenv_values(env_file)
            gemini_key = gemini_key or env_vals.get("GOOGLE_API_KEY")
            anthropic_key = anthropic_key or env_vals.get("ANTHROPIC_API_KEY")
            openai_key = openai_key or env_vals.get("OPENAI_API_KEY")

    if not any([gemini_key, anthropic_key, openai_key]):
        return "❌ No AI API key found. Please configure GOOGLE_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY."

    # Select provider (prefer Gemini for parity with Discord bot)
    provider = "gemini" if gemini_key else ("anthropic" if anthropic_key else "openai")
    
    # 3. Build the prompt
    system_prompt = f"""You are OS Twin Assistant, a helpful AI that answers questions about ongoing software projects managed by the Ostwin multi-agent war-room orchestrator.

You have access to the current state of all plans, war-rooms, and message history. Use the context below to answer the user's question accurately and concisely. If you don't have enough information, say so.

--- CONTEXT ---
PLANS:
{plans}

WAR-ROOMS:
{rooms}

STATS:
{stats}

RECENT RELEVANT MESSAGES:
{search}
--- END CONTEXT ---

Format your response for {platform} (markdown). Keep it concise — aim for 1-3 paragraphs max."""

    # 4. Call AI provider
    try:
        if provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=gemini_key)
            response = await llm.ainvoke([("system", system_prompt), ("human", question)])
            return response.content
        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model="claude-3-haiku-20240307", anthropic_api_key=anthropic_key)
            response = await llm.ainvoke([("system", system_prompt), ("human", question)])
            return response.content
        elif provider == "openai":
            # Assuming langchain-openai will be installed
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini", api_key=openai_key)
            response = await llm.ainvoke([("system", system_prompt), ("human", question)])
            return response.content
    except Exception as e:
        logger.error(f"Error calling AI provider {provider}: {e}")
        return f"❌ Error synthesizing answer via {provider}: {e}"

    return "❌ No supported AI provider configured."
