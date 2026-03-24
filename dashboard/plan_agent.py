"""
Plan Agent — deepagents-powered plan refinement.

Uses create_deep_agent() to help users refine rough ideas into
properly structured plans with Epics, acceptance criteria,
and working directories.
"""

import os
import json
import logging
import re
from pathlib import Path
from typing import Optional, AsyncIterator

from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

logger = logging.getLogger(__name__)

def _load_available_roles(agents_dir: Optional[Path] = None) -> str:
    """Read roles from registry.json and format them for the prompt."""
    if not agents_dir:
        return "Available roles: engineer, qa, architect, or any custom role you define."

    registry_file = agents_dir / "roles" / "registry.json"
    if not registry_file.exists():
        return "Available roles: engineer, qa, architect, or any custom role you define."

    try:
        registry = json.loads(registry_file.read_text())
        roles = registry.get("roles", [])
        if not roles:
            return "Available roles: engineer, qa, architect, or any custom role you define."

        lines = ["Available registered roles (PREFER these when they fit):"]
        for role in roles:
            name = role.get("name", "unknown")
            desc = role.get("description", "")
            caps = role.get("capabilities", [])
            caps_str = f" — capabilities: {', '.join(caps)}" if caps else ""
            lines.append(f"  - **{name}**: {desc}{caps_str}")

        lines.append("")
        lines.append("You MAY also define custom roles (e.g., `researcher`, `technical-writer`, `data-scientist`) when no registered role fits the epic's needs.")
        lines.append("Custom roles will be dynamically resolved at runtime via the ephemeral agent system.")
        return "\n".join(lines)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read roles registry: {e}")
        return "Available roles: engineer, qa, architect, or any custom role you define."


def get_system_prompt(plans_dir: Optional[Path] = None, agents_dir: Optional[Path] = None) -> str:
    """Generate the system prompt dynamically based on the plan template."""
    plan_format_spec = "Error: Template not found."
    if plans_dir:
        template_path = plans_dir / "PLAN.template.md"
        if template_path.exists():
            plan_format_spec = template_path.read_text()
        else:
            logger.warning(f"Plan template not found at {template_path}")
            plan_format_spec = f"Template not found at {template_path}"
    else:
        logger.warning("plans_dir not provided, cannot load PLAN.template.md")
        plan_format_spec = "Plans directory not configured."

    # Resolve agents_dir from plans_dir if not provided
    if not agents_dir and plans_dir:
        agents_dir = plans_dir.parent

    # Substitute {{AVAILABLE_ROLES}} placeholder with dynamic roles
    roles_text = _load_available_roles(agents_dir)
    plan_format_spec = plan_format_spec.replace("{{AVAILABLE_ROLES}}", roles_text)

    return f"""\
You are a **Plan Architect** for OS Twin — an AI-powered development orchestration system.

Your job is to take the user's rough idea and refine it into a structured plan that can be
executed by autonomous agents inside **war-rooms**.

## RESPONSE STRUCTURE

Your response MUST be divided into these clear sections with these exact headers:

### SUMMARY
Provide a concise overview of what you are proposing or changing in this turn.

### ACTIONS
Provide a structured, parseable list of file operations. Wrap the entire actions list in `<plan>` tags.
Organize actions into logical sections using `### Section Name`.
Use this exact format for actions:
- CREATE <path>
- UPDATE <path>
- DELETE <path>

Example:
<plan>
### Backend Changes
- UPDATE dashboard/api.py
- CREATE dashboard/models.py

### Frontend Changes
- UPDATE nextjs/src/app/page.tsx
</plan>

If no file operations are proposed, state "None".

### PLAN
The complete, updated markdown plan following the template and rules below.

## OUTPUT FORMAT AND INSTRUCTIONS

You MUST produce a plan strictly following the format and rules defined in the template below.
The template includes both instructions (in HTML comments or text) and the exact structure to use.
Pay special attention to the dynamic Roles and Lifecycle sections.

```markdown
{plan_format_spec}
```

## ROLE SELECTION RULES

1. **Always prefer** using the available registered roles listed in the template above.
2. You MAY define custom roles (e.g., "researcher", "technical-writer", "data-scientist") when no registered role fits the epic's needs.
3. Custom roles will be dynamically resolved at runtime via the ephemeral agent system.
4. Lifecycle state names MUST match the role names used in the Roles: directive.

## ADDITIONAL RULES

1. If the user provides an existing plan, improve it while preserving their intent.
2. If the user asks to modify a specific part, change only that part.
3. Be concise, technical, and precise. Write like a senior engineering lead scoping work.
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

    # Resolve agents_dir from plans_dir
    agents_dir = plans_dir.parent if plans_dir else None

    agent = create_deep_agent(
        model=chat_model,
        tools=[read_existing_plan],
        system_prompt=get_system_prompt(plans_dir, agents_dir=agents_dir),
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
) -> AsyncIterator[dict]:
    """Stream the plan agent's response with section labels.

    Yields dictionaries containing 'token' and 'section'.

    Args:
        user_message: User's refinement instruction.
        plan_content: Current editor content.
        chat_history: Previous turns.
        model: LLM model to use.
        plans_dir: Path to plans directory.

    Returns:
        AsyncIterator of dictionaries: {"token": str, "section": Optional[str]}
    """
    agent = create_plan_agent(model=model, plans_dir=plans_dir)
    messages = build_messages(user_message, plan_content, chat_history)

    current_section = None
    # We use a small buffer to detect headers that might be split across chunks
    header_buffer = ""

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
                    tokens = []
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("text"):
                                tokens.append(block["text"])
                            elif isinstance(block, str):
                                tokens.append(block)
                    elif isinstance(content, str):
                        tokens.append(content)

                    for token in tokens:
                        header_buffer += token
                        
                        # Detect the start of a Plan section (# Plan: ...)
                        if not current_section or current_section != "PLAN":
                            plan_title_match = re.search(r"(?:^|\n)#\s+Plan:\s+(.*)", header_buffer)
                            if plan_title_match:
                                current_section = "PLAN"
                                header_buffer = header_buffer.split(plan_title_match.group(0))[-1]

                        # Detect section headers: ### SECTION NAME
                        header_match = re.search(r"###\s+([A-Za-z0-9_\s\-]+)", header_buffer)
                        if header_match:
                            section_name = header_match.group(1).strip()
                            sn_upper = section_name.upper()
                            
                            # Standardize section names for consistent parsing
                            if "SUMMARY" in sn_upper: current_section = "SUMMARY"
                            elif "ACTIONS" in sn_upper: current_section = "ACTIONS"
                            elif "PLAN" in sn_upper: current_section = "PLAN"
                            else: current_section = section_name # e.g. "Backend Changes"

                            # Clear buffer up to the header to avoid re-triggering
                            header_buffer = header_buffer.split(header_match.group(0))[-1]
                        
                        # Detect <plan> tags for fine-grained structured output
                        if "<plan>" in header_buffer:
                            # If we see <plan>, we're definitely in an action-oriented section
                            if current_section not in ("ACTIONS", "PLAN"):
                                # If it's not the main PLAN section, it's likely the ACTIONS section
                                if current_section != "SUMMARY":
                                    current_section = "ACTIONS"
                            header_buffer = header_buffer.split("<plan>")[-1]
                        
                        # Keep buffer size manageable
                        if len(header_buffer) > 100:
                            header_buffer = header_buffer[-100:]

                        yield {"token": token, "section": current_section}
    except Exception as e:
        logger.error("Plan agent streaming error: %s", e)
        yield {"token": f"\n\n[Error: {str(e)}]", "section": "error"}
