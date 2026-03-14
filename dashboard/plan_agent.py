"""
Plan Agent — deepagents-powered plan refinement.

Uses create_deep_agent() to help users refine rough ideas into
properly structured plans with Epics, acceptance criteria,
and working directories.
"""

import os
import logging
from pathlib import Path
from typing import Optional, AsyncIterator

from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

logger = logging.getLogger(__name__)

# ── Plan format specification ──────────────────────────────────────

PLAN_FORMAT_SPEC = """\
# Plan: <Title>

## Config
working_dir: /path/to/your/project

## Epic: EPIC-001 — <Epic Title>

<Description of what the engineer should build.>
<Be specific about modules, APIs, or structures to create.>
<The engineer will decompose this into sub-tasks and create TASKS.md.>

Acceptance criteria:
- <Concrete, testable criterion 1>
- <Concrete, testable criterion 2>

## Epic: EPIC-002 — <Second Epic Title>

<Description...>

Acceptance criteria:
- <criterion>
"""

SYSTEM_PROMPT = f"""\
You are a **Plan Architect** for OS Twin — an AI-powered development orchestration system.

Your job is to take the user's rough idea and refine it into a structured plan that can be
executed by autonomous engineer and QA agents.

## OUTPUT FORMAT

You MUST produce a plan in EXACTLY this format:

```
{PLAN_FORMAT_SPEC}
```

## RULES

1. Every plan MUST start with `# Plan: <Title>`
2. Every plan MUST have `## Config` with `working_dir:` (use `.` if not specified)
3. Break the work into **2–5 Epics** (`## Epic: EPIC-XXX — Title`)
4. Number epics sequentially: EPIC-001, EPIC-002, etc.
5. Each Epic MUST have **Acceptance criteria:** as a bulleted list
6. Be specific and actionable — an engineer agent reads this
7. Do NOT include actual code — only high-level descriptions
8. Respect dependency order — foundational epics first
9. If the user provides an existing plan, improve it while preserving their intent
10. If the user asks to modify a specific part, change only that part

## TONE

Be concise, technical, and precise. Write like a senior engineering lead scoping work.
"""


# ── Auto-detect available AI provider ──────────────────────────────

def detect_model() -> tuple[str, str]:
    """Pick the best available model based on which API keys are set.

    Returns:
        A tuple of (model_name, provider) for langchain's init_chat_model.
    """
    if os.environ.get("GOOGLE_API_KEY"):
        return ("gemini-3.1-pro-preview", "google_genai")
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ("claude-sonnet-4-6", "anthropic")
    if os.environ.get("OPENAI_API_KEY"):
        return ("gpt-4o", "openai")
    raise RuntimeError(
        "No AI API key found. Set GOOGLE_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY in ~/.ostwin/.env"
    )


def _resolve_model(model_str: str = ""):
    """Resolve a model string into an initialized ChatModel.

    If model_str is empty, auto-detects from environment.
    If model_str contains ':', splits as 'provider:model'.
    Otherwise uses init_chat_model's auto-detection.
    """
    from langchain.chat_models import init_chat_model

    if not model_str:
        model_name, provider = detect_model()
        return init_chat_model(model_name, model_provider=provider)

    if ":" in model_str:
        provider, model_name = model_str.split(":", 1)
        # Normalize provider names
        provider_map = {
            "google-genai": "google_genai",
            "google-vertexai": "google_vertexai",
        }
        provider = provider_map.get(provider, provider)
        return init_chat_model(model_name, model_provider=provider)

    return init_chat_model(model_str)


# ── Agent factory ──────────────────────────────────────────────────

def create_plan_agent(
    model: str = "",
    plans_dir: Optional[Path] = None,
):
    """Create a deepagent configured for plan refinement.

    Args:
        model: LLM model identifier. Supports formats:
               - Empty string: auto-detect from env vars
               - "provider:model" (e.g. "google-genai:gemini-2.5-flash")
               - Plain model name (e.g. "claude-sonnet-4-6")
        plans_dir: Path to the plans directory for the read_existing_plan tool.

    Returns:
        A compiled LangGraph agent.
    """
    from langchain_core.tools import tool as lc_tool

    _plans_dir = plans_dir

    @lc_tool
    def read_existing_plan(plan_id: str) -> str:
        """Read the current content of a plan file by its ID.

        Use this when the user references an existing plan or asks to
        review/modify a previously saved plan.

        Args:
            plan_id: The plan identifier (filename stem without .md).

        Returns:
            The full plan file content, or an error message.
        """
        if not _plans_dir:
            return "Error: Plans directory not configured."
        plan_file = _plans_dir / f"{plan_id}.md"
        if not plan_file.exists():
            return f"Error: Plan '{plan_id}' not found."
        return plan_file.read_text()

    chat_model = _resolve_model(model)
    logger.info("Plan agent using model: %s", type(chat_model).__name__)

    agent = create_deep_agent(
        model=chat_model,
        tools=[read_existing_plan],
        system_prompt=SYSTEM_PROMPT,
    )

    return agent


# ── Invoke helpers ─────────────────────────────────────────────────

def build_messages(
    user_message: str,
    plan_content: str = "",
    chat_history: list[dict] | None = None,
) -> list:
    """Build the message list for the agent invocation.

    Args:
        user_message: The user's latest instruction.
        plan_content: Current editor content to provide as context.
        chat_history: Previous conversation turns [{role, content}, ...].

    Returns:
        List of LangChain message objects.
    """
    messages = []

    # Inject current plan as system context
    if plan_content and plan_content.strip():
        messages.append(
            SystemMessage(content=f"The user's current plan in the editor:\n\n```markdown\n{plan_content}\n```")
        )

    # Add chat history
    if chat_history:
        for msg in chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    # Add the latest user message
    messages.append(HumanMessage(content=user_message))

    return messages


async def refine_plan(
    user_message: str,
    plan_content: str = "",
    chat_history: list[dict] | None = None,
    model: str = "",
    plans_dir: Optional[Path] = None,
) -> str:
    """Invoke the plan agent and return the refined plan text.

    Args:
        user_message: User's refinement instruction.
        plan_content: Current editor content.
        chat_history: Previous turns.
        model: LLM model to use.
        plans_dir: Path to plans directory.

    Returns:
        The agent's response text.
    """
    agent = create_plan_agent(model=model, plans_dir=plans_dir)
    messages = build_messages(user_message, plan_content, chat_history)

    result = await agent.ainvoke({"messages": messages})

    # Extract the last AI message
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and msg.content:
            return msg.content

    return "Error: No response from plan agent."


async def refine_plan_stream(
    user_message: str,
    plan_content: str = "",
    chat_history: list[dict] | None = None,
    model: str = "",
    plans_dir: Optional[Path] = None,
) -> AsyncIterator[str]:
    """Stream the plan agent's response token-by-token.

    Yields individual content chunks as they arrive from the LLM.

    Args:
        user_message: User's refinement instruction.
        plan_content: Current editor content.
        chat_history: Previous turns.
        model: LLM model to use.
        plans_dir: Path to plans directory.

    Returns:
        AsyncIterator of string tokens.
    """
    agent = create_plan_agent(model=model, plans_dir=plans_dir)
    messages = build_messages(user_message, plan_content, chat_history)

    try:
        async for event in agent.astream_events(
            {"messages": messages},
            version="v2",
        ):
            kind = event.get("event", "")
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    content = chunk.content
                    # Gemini returns content as a list of blocks:
                    #   [{"type": "text", "text": "..."}]
                    # Other providers return a plain string.
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("text"):
                                yield block["text"]
                            elif isinstance(block, str):
                                yield block
                    elif isinstance(content, str):
                        yield content
    except Exception as e:
        logger.error("Plan agent streaming error: %s", e)
        yield f"\n\n[Error: {str(e)}]"
