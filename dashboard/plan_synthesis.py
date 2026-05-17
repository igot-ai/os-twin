"""Single-step plan synthesis from a brainstorm thread.

This is the Python port of the TypeScript `ostwin_create_plan` opencode tool
(``dashboard/opencode_tools.py:_tool_create_plan``).  promote_thread used to
go through the master agent, which fires ``ostwin_create_plan`` server-side
(producing plan #1 with epics) and then *also* falls back to writing a
prose-only second plan from Python (plan #2 with zero epics).  We bypass the
master agent entirely and call this function directly so exactly one plan is
allocated per Promote click.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import dashboard.global_state as global_state
from dashboard.api_utils import PLANS_DIR
from dashboard.master_agent import get_opencode_client
from dashboard.plan_agent import get_system_prompt
from dashboard.routes.plans import create_plan_on_disk

logger = logging.getLogger(__name__)

_EPIC_RE = re.compile(r"EPIC-\d{3}")


async def synthesize_plan_from_thread(
    thread_id: str,
    chat_history: List[Dict[str, str]],
    title: str,
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    skel = create_plan_on_disk(
        title=title,
        content="",
        working_dir=working_dir,
        thread_id=thread_id,
    )
    plan_id = skel["plan_id"]
    resolved_working_dir = skel["working_dir"]
    plan_file = PLANS_DIR / f"{plan_id}.md"

    try:
        system_prompt = get_system_prompt(PLANS_DIR, mode="worker")
        client = get_opencode_client()

        history_blob = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in chat_history
        )
        task_message = (
            f"Draft a new plan based on this brainstorming conversation: {title}\n\n"
            f"Working directory: {resolved_working_dir}\n"
            f"Plan ID: {plan_id}\n\n"
            f"Conversation:\n{history_blob}\n\n"
            "INSTRUCTIONS:\n"
            f"1. Read the current skeleton plan file at: {plan_file}\n"
            "2. Write a COMPLETE, properly structured plan to that file "
            "(overwriting the skeleton).\n"
            "   - Use a SHORT descriptive title (3-8 words), NOT the raw user idea.\n"
            "   - Create 3-8 epics with SHORT meaningful names.\n"
            "   - Each epic MUST have: Roles, Objective, Lifecycle, Definition of Done, "
            "Acceptance Criteria, Tasks.\n"
            "   - Include proper depends_on chains between epics.\n"
            f'3. After writing, call ostwin_register_plan with plan_id="{plan_id}".\n'
            "4. Return a 2-3 sentence summary of what you drafted.\n"
        )

        child = await client.post("/session", body={}, cast_to=object)
        child_id = child.get("id") if isinstance(child, dict) else None
        if not child_id:
            raise RuntimeError(
                f"Failed to spawn worker child session for plan {plan_id}: {child!r}"
            )

        resp = await client.post(
            f"/session/{child_id}/message",
            body={
                "agent": "ostwin-worker",
                "system": system_prompt,
                "parts": [{"type": "text", "text": task_message}],
            },
            cast_to=object,
        )

        parts = resp.get("parts", []) if isinstance(resp, dict) else []
        worker_summary = "\n".join(
            p.get("text", "")
            for p in parts
            if isinstance(p, dict) and p.get("type") == "text"
        ).strip()

        content = plan_file.read_text() if plan_file.exists() else ""
        epic_count = len(_EPIC_RE.findall(content))

        if epic_count == 0:
            raise RuntimeError(
                f"Worker session {child_id} finished but plan {plan_id} has no epics. "
                f"Worker summary: {worker_summary[:200] or '(empty)'}"
            )

        store = global_state.store
        if store:
            try:
                store.index_plan(
                    plan_id=plan_id,
                    title=title,
                    content=content,
                    epic_count=epic_count,
                    filename=f"{plan_id}.md",
                    status="draft",
                    created_at=skel.get("created_at"),
                    file_mtime=plan_file.stat().st_mtime,
                )
                try:
                    from dashboard.zvec_store import OSTwinStore

                    for ep in OSTwinStore._parse_plan_epics(content, plan_id):
                        try:
                            store.index_epic(plan_id=plan_id, **ep)
                        except Exception as ee:
                            logger.warning("Failed to index epic for %s: %s", plan_id, ee)
                except Exception as e:
                    logger.warning("Failed to parse/index epics for %s: %s", plan_id, e)
            except Exception as e:
                logger.warning("Failed to re-index plan %s in zvec: %s", plan_id, e)

        return {
            **skel,
            "epic_count": epic_count,
            "worker_summary": worker_summary,
            "child_session_id": child_id,
        }
    except Exception:
        _cleanup_skeleton(plan_id)
        raise


def _cleanup_skeleton(plan_id: str) -> None:
    for suffix in (".md", ".meta.json", ".roles.json"):
        p = PLANS_DIR / f"{plan_id}{suffix}"
        if p.exists():
            try:
                p.unlink()
            except Exception as e:
                logger.warning("Failed to delete %s: %s", p, e)
