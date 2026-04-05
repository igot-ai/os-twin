"""
Plan Agent — deepagents-powered plan refinement.

Uses create_deep_agent() to help users refine rough ideas into
properly structured plans with Epics, acceptance criteria,
and working directories.
"""

import os
import json
import re
import logging
from pathlib import Path
from typing import Optional, AsyncIterator, Dict, Any

from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

logger = logging.getLogger(__name__)


def parse_structured_response(text: str) -> Dict[str, Any]:
    """Parse the structured Markdown response from the Plan Architect."""
    sections = {"explanation": "", "actions": [], "plan": "", "full_response": text}

    # Split by headers # EXPLANATION, # ACTIONS, # PLAN (case-insensitive, support multiple #)
    pattern = r"^#+\s+(EXPLANATION|ACTIONS|PLAN)\b"
    parts = re.split(pattern, text, flags=re.MULTILINE | re.IGNORECASE)

    # Re-split returns [prefix, header1, content1, header2, content2, ...]
    for i in range(1, len(parts), 2):
        header = parts[i].upper()
        content = parts[i + 1].strip()

        if header == "EXPLANATION":
            sections["explanation"] = (sections["explanation"] + "\n" + content).strip()
        elif header == "ACTIONS":
            # Parse lines like "- ACTION: path/to/file"
            lines = content.splitlines()
            for line in lines:
                # Support formats: "- CREATE: path", "UPDATE: path", "- [DELETE] path"
                m = re.search(
                    r"(CREATE|UPDATE|DELETE)[:\s\-\]\[]+([^\s\]]+)",
                    line.strip(),
                    re.IGNORECASE,
                )
                if m:
                    sections["actions"].append(
                        {"action": m.group(1).upper(), "path": m.group(2).strip()}
                    )
        elif header == "PLAN":
            sections["plan"] = (sections["plan"] + "\n" + content).strip()

    # Fallback: if we didn't find specific sections but have text,
    # and it looks like a plan, put it in the 'plan' field for backward compatibility.
    if not sections["plan"] and not sections["explanation"] and text.strip():
        if "# Plan" in text or "## Epics" in text:
            sections["plan"] = text

    return sections


def _load_available_roles(agents_dir: Optional[Path] = None) -> str:
    """Read roles from registry.json and format them for the prompt."""
    if not agents_dir:
        return (
            "Available roles: engineer, qa, architect, or any custom role you define."
        )

    registry_file = agents_dir / "roles" / "registry.json"
    if not registry_file.exists():
        return (
            "Available roles: engineer, qa, architect, or any custom role you define."
        )

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
        lines.append(
            "You MAY also define custom roles (e.g., `researcher`, `technical-writer`, `data-scientist`) when no registered role fits the epic's needs."
        )
        lines.append(
            "Custom roles will be dynamically resolved at runtime via the ephemeral agent system."
        )
        return "\n".join(lines)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read roles registry: {e}")
        return (
            "Available roles: engineer, qa, architect, or any custom role you define."
        )


def get_system_prompt(
    plans_dir: Optional[Path] = None, agents_dir: Optional[Path] = None,
    working_dir: Optional[str] = None,
) -> str:
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

    # Resolve actual project working directory
    if working_dir:
        project_dir = working_dir
    else:
        # OSTWIN_PROJECT_DIR is set by `ostwin dashboard --project-dir`
        # This is the directory where the user ran `ostwin init`
        env_project = os.environ.get("OSTWIN_PROJECT_DIR")
        if env_project:
            project_dir = str(Path(env_project) / "projects")
        else:
            from dashboard.api_utils import PROJECT_ROOT
            project_dir = str(PROJECT_ROOT / "projects")

    return f"""\
You are a **Plan Architect** for OS Twin — an AI-powered development orchestration system.

Your job is to take the user's rough idea and refine it into a structured plan that can be
executed by autonomous agents inside **war-rooms**.

## OUTPUT FORMAT AND INSTRUCTIONS

You MUST separate your output into the following three labeled sections in this exact order:

# EXPLANATION
A brief, high-level summary of the changes or improvements you've made to the plan.

# ACTIONS
A list of discrete file operations required to implement the refinement.
Format each line as: `- ACTION: path/to/file` (where ACTION is CREATE, UPDATE, or DELETE).
If you are refining an existing plan, ALWAYS include `- UPDATE: PLAN.md`.
Example:
- CREATE: dashboard/models.py
- UPDATE: PLAN.md

# PLAN
The full, updated plan content strictly following the template format below.

## RULES
1. ONLY output the three sections above. Do NOT include any introductory or concluding text.
2. Each section MUST start with its corresponding '#' header on a new line.
3. The `# ACTIONS` section MUST list one action per line for all files created or modified.
4. The `# PLAN` section MUST contain the full, valid Markdown content of the plan, starting from its title.
5. Maintain consistency and accuracy in all file paths.

## PLAN TEMPLATE
Strictly follow the structure and rules defined in the template below.
Pay special attention to the dynamic Roles and Lifecycle sections.

```markdown
{plan_format_spec}
```

## ROLE SELECTION RULES

1. **Always prefer** using the available registered roles listed in the template above.
2. You MAY define custom roles (e.g., "researcher", "technical-writer", "data-scientist") when no registered role fits the epic's needs.
3. Custom roles will be dynamically resolved at runtime via the ephemeral agent system.
4. Lifecycle state names MUST match the role names used in the Roles: directive.

## PROJECT CONTEXT

The project base directory is: `{project_dir}`
For `> Project:` and `working_dir:` in the Config section, use a short kebab-case subfolder name under this base.
Example: if the user wants to build a "YouTube Clone", set `working_dir: {project_dir}/youtube-clone`.
Do NOT invent arbitrary paths — always use `{project_dir}/<short-name>`.

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
        return ("gemini-3-flash-preview", "google_genai")
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
    working_dir: Optional[str] = None,
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
    logger.info(f"System prompt,: {get_system_prompt(plans_dir, agents_dir=agents_dir)}")
    print(f"System prompt,: {get_system_prompt(plans_dir, agents_dir=agents_dir)}")

    agent = create_deep_agent(
        model=chat_model,
        tools=[read_existing_plan],
        system_prompt=get_system_prompt(plans_dir, agents_dir=agents_dir, working_dir=working_dir),
    )

    return agent


# ── Invoke helpers ─────────────────────────────────────────────────


def _make_human_content(text: str, images: list[dict] | None = None) -> str | list:
    """Build HumanMessage content — plain string or multimodal blocks."""
    if not images:
        return text
    blocks: list[dict] = []
    if text:
        blocks.append({"type": "text", "text": text})
    for img in images:
        url = img.get("url", "")
        if url:
            blocks.append({"type": "image_url", "image_url": {"url": url}})
    return blocks if blocks else text


def build_messages(
    user_message: str,
    plan_content: str = "",
    chat_history: list[dict] | None = None,
    images: list[dict] | None = None,
) -> list:
    """Build the message list for the agent invocation.

    Args:
        user_message: The user's latest instruction.
        plan_content: Current editor content to provide as context.
        chat_history: Previous conversation turns [{role, content}, ...].
        images: Optional images for the latest user message.

    Returns:
        List of LangChain message objects.
    """
    messages = []

    # Inject current plan as system context
    if plan_content and plan_content.strip():
        messages.append(
            SystemMessage(
                content=f"The user's current plan in the editor:\n\n```markdown\n{plan_content}\n```"
            )
        )

    # Add chat history
    if chat_history:
        for msg in chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                hist_images = msg.get("images")
                messages.append(HumanMessage(content=_make_human_content(content, hist_images)))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    # Add the latest user message
    messages.append(HumanMessage(content=_make_human_content(user_message, images)))

    return messages


async def refine_plan(
    user_message: str,
    plan_content: str = "",
    chat_history: list[dict] | None = None,
    model: str = "",
    plans_dir: Optional[Path] = None,
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Invoke the plan agent and return the refined plan structured data.

    Args:
        user_message: User's refinement instruction.
        plan_content: Current editor content.
        chat_history: Previous turns.
        model: LLM model to use.
        plans_dir: Path to plans directory.
        working_dir: Target project directory for this plan.

    Returns:
        A dictionary with explanation, actions, and plan content.
    """
    agent = create_plan_agent(model=model, plans_dir=plans_dir, working_dir=working_dir)
    messages = build_messages(user_message, plan_content, chat_history)

    result = await agent.ainvoke({"messages": messages})

    # Extract the last AI message
    raw_content = ""
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and msg.content:
            content = msg.content
            if isinstance(content, list):
                # Handle Gemini blocks
                raw_content = "".join(
                    [
                        b["text"] if isinstance(b, dict) and "text" in b else str(b)
                        for b in content
                    ]
                )
            else:
                raw_content = content
            break

    if not raw_content:
        return {"error": "No response from plan agent."}

    return parse_structured_response(raw_content)


async def refine_plan_stream(
    user_message: str,
    plan_content: str = "",
    chat_history: list[dict] | None = None,
    model: str = "",
    plans_dir: Optional[Path] = None,
    working_dir: Optional[str] = None,
) -> AsyncIterator[str]:
    """Stream the plan agent's response token-by-token.

    Args:
        user_message: User's refinement instruction.
        plan_content: Current editor content.
        chat_history: Previous turns.
        model: LLM model to use.
        plans_dir: Path to plans directory.
        working_dir: Target project directory for this plan.

    Returns:
        AsyncIterator of string tokens.
    """
    agent = create_plan_agent(model=model, plans_dir=plans_dir, working_dir=working_dir)
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

async def summarize_plan(
    plan_content: str,
    model: str = "",
    plans_dir: Optional[Path] = None,
) -> str:
    """Invoke the agent to summarize a drafted plan."""
    llm = _resolve_model(model)
    prompt = (
        "You are an AI assistant. Please provide a concise summary (3-5 bullet points) "
        "of the following software project plan. Highlight the main objective, "
        "the key epics, and any notable architecture/roles.\n\n"
        "Plan:\n"
        f"{plan_content}"
    )
    from langchain_core.messages import HumanMessage
    result = await llm.ainvoke([HumanMessage(content=prompt)])
    content = result.content
    if isinstance(content, list):
        content = "".join([b["text"] if isinstance(b, dict) and "text" in b else str(b) for b in content])
    return content.strip()


BRAINSTORM_SYSTEM_PROMPT = """\
You are an expert brainstorming partner and system architect.
Your goal is to help the user explore ideas, refine their problem space,
understand their target users, and map out their tech stack and architecture.

You DO NOT need to output structured plans (no EXPLANATION, ACTIONS, or PLAN sections).
Just have a natural, helpful conversation.
Ask clarifying questions to dig deeper into the user's intent.
Provide suggestions, trade-offs, and examples to guide them.
Be concise but insightful.
"""

def create_brainstorm_agent(model: str = ""):
    """Create a deepagent configured for pure brainstorming conversation.

    Args:
        model: LLM model identifier. Supports formats:
               - Empty string: auto-detect from env vars
               - "provider:model"
               - Plain model name

    Returns:
        A compiled LangGraph agent without tools.
    """
    chat_model = _resolve_model(model)
    logger.info("Brainstorm agent using model: %s", type(chat_model).__name__)

    agent = create_deep_agent(
        model=chat_model,
        tools=[],
        system_prompt=BRAINSTORM_SYSTEM_PROMPT,
    )

    return agent

async def brainstorm_stream(
    user_message: str,
    chat_history: list[dict] | None = None,
    model: str = "",
    images: list[dict] | None = None,
) -> AsyncIterator[str]:
    """Stream the brainstorm agent's response token-by-token.

    Args:
        user_message: User's next instruction/message.
        chat_history: Previous conversation turns [{role, content}, ...].
        model: LLM model to use.
        images: Optional images for the current message.

    Returns:
        AsyncIterator of string tokens.
    """
    agent = create_brainstorm_agent(model=model)
    messages = build_messages(user_message, plan_content="", chat_history=chat_history, images=images)

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
        logger.error("Brainstorm agent streaming error: %s", e)
        yield f"\n\n[Error: {str(e)}]"
