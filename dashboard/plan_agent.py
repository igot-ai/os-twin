"""
Plan Agent — deepagents-powered plan refinement.

Uses deepagents CLI as a subprocess to help users refine rough ideas into
properly structured plans with Epics, acceptance criteria,
and working directories.
"""

import os
import json
import re
import logging
import asyncio
import uuid
from pathlib import Path
from typing import Optional, AsyncIterator, Dict, Any

logger = logging.getLogger(__name__)

def parse_structured_response(text: str) -> Dict[str, Any]:
    """Parse the structured Markdown response from the Plan Architect."""
    sections = {
        "explanation": "",
        "actions": [],
        "plan": "",
        "full_response": text
    }

    # Split by headers # EXPLANATION, # ACTIONS, # PLAN (case-insensitive, support multiple #)
    pattern = r"^#+\s+(EXPLANATION|ACTIONS|PLAN)\b"
    parts = re.split(pattern, text, flags=re.MULTILINE | re.IGNORECASE)

    # Re-split returns [prefix, header1, content1, header2, content2, ...]
    for i in range(1, len(parts), 2):
        header = parts[i].upper()
        content = parts[i+1].strip()

        if header == "EXPLANATION":
            sections["explanation"] = (sections["explanation"] + "\n" + content).strip()
        elif header == "ACTIONS":
            # Parse lines like "- ACTION: path/to/file"
            lines = content.splitlines()
            for line in lines:
                # Support formats: "- CREATE: path", "UPDATE: path", "- [DELETE] path"
                m = re.search(r"(CREATE|UPDATE|DELETE)[:\s\-\]\[]+([^\s\]]+)", line.strip(), re.IGNORECASE)
                if m:
                    sections["actions"].append({
                        "action": m.group(1).upper(),
                        "path": m.group(2).strip()
                    })
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

## ADDITIONAL RULES

1. If the user provides an existing plan, improve it while preserving their intent.
2. If the user asks to modify a specific part, change only that part.
3. Be concise, technical, and precise. Write like a senior engineering lead scoping work.
"""

def detect_model() -> str:
    """Pick the best available model based on which API keys are set.
    Uses deepagents provider formatting natively.
    """
    # Overriding to force the correct provider/key despite environment leaks
    os.environ["GOOGLE_API_KEY"] = "AIzaSyDxJlQhiEfW_LYHHzJICY7bkFkasnKk5e0"
    return "google_genai:gemini-3.1-pro-preview"

def build_prompt_text(
    user_message: str,
    plan_content: str = "",
    chat_history: list[dict] | None = None,
    plans_dir: Optional[Path] = None,
    agents_dir: Optional[Path] = None,
) -> str:
    """Build the raw prompt text to send to deepagents CLI."""
    lines = []
    
    # 1. System Prompt
    lines.append(get_system_prompt(plans_dir, agents_dir))
    lines.append("\n" + "="*40 + "\n")
    
    # 2. Inject current plan as system context
    if plan_content and plan_content.strip():
        lines.append("The user's current plan in the editor:\n\n```markdown\n" + plan_content + "\n```")
        lines.append("\n" + "="*40 + "\n")
        
    # 3. Add chat history
    if chat_history:
        for msg in chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"[{role.upper()}]:\n{content}\n")
            
    # 4. Add the latest user message
    lines.append(f"[USER]:\n{user_message}\n")
    
    # 5. Output instruction
    lines.append("\nReturn ONLY the markdown plan, with no additional conversational text or wrapper text.")
    
    return "\n".join(lines)


async def refine_plan(
    user_message: str,
    plan_content: str = "",
    chat_history: list[dict] | None = None,
    model: str = "",
    plans_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Invoke the plan agent and return the refined plan structured data.

    Args:
        user_message: User's refinement instruction.
        plan_content: Current editor content.
        chat_history: Previous turns.
        model: LLM model to use.
        plans_dir: Path to plans directory.

    Returns:
        A dictionary with explanation, actions, and plan content.
    """
    agent = create_plan_agent(model=model, plans_dir=plans_dir)
    messages = build_messages(user_message, plan_content, chat_history)

    result = await agent.ainvoke({"messages": messages})

    # Extract the last AI message
    raw_content = ""
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and msg.content:
            content = msg.content
            if isinstance(content, list):
                # Handle Gemini blocks
                raw_content = "".join([b["text"] if isinstance(b, dict) and "text" in b else str(b) for b in content])
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
) -> AsyncIterator[str]:
    """Non-streaming wrapper — yields the full result as a single JSON chunk."""
    import json as _json
    result = await refine_plan(
        user_message=user_message,
        plan_content=plan_content,
        chat_history=chat_history,
        model=model,
        plans_dir=plans_dir
    )
    yield _json.dumps(result)

async def summarize_plan(
    plan_content: str,
    model: str = "",
    plans_dir: Optional[Path] = None,
) -> str:
    """Invoke the agent to summarize a drafted plan."""
    if not model:
        model = detect_model()

    agents_dir = plans_dir.parent if plans_dir else None

    prompt = (
        "You are an AI assistant. Please provide a concise summary (3-5 bullet points) "
        "of the following software project plan. Highlight the main objective, "
        "the key epics, and any notable architecture/roles.\n\n"
        "Plan:\n"
        f"{plan_content}"
    )

    temp_prompt_path = Path(f"/tmp/plan-prompt-{uuid.uuid4().hex}.txt")
    temp_prompt_path.write_text(prompt)

    deepagents_cmd = "deepagents"
    if agents_dir:
        local_agent = agents_dir / "bin" / "agent"
        if local_agent.exists():
            deepagents_cmd = str(local_agent)

    try:
        env = os.environ.copy()
        proc = await asyncio.create_subprocess_shell(
            f"\"{deepagents_cmd}\" -n \"$(cat '{temp_prompt_path}')\" -M \"{model}\" -q --auto-approve",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            error_msg = stderr.decode().strip()
            logger.error(f"Summarize agent CLI failed ({proc.returncode}): {error_msg}")
            return f"Summary unavailable. (Error: {proc.returncode})"

        result = stdout.decode().strip()

        # Clean up tags if present
        if "<plan>" in result and "</plan>" in result:
             result = result.split("<plan>")[1].split("</plan>")[0].strip()

        return result
    finally:
        if temp_prompt_path.exists():
            temp_prompt_path.unlink()
