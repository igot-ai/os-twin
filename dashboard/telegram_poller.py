import asyncio
import httpx
import logging
import json
import os
import signal
import uuid
from pathlib import Path
from datetime import datetime, timezone
import dashboard.global_state as global_state
from dashboard.telegram_bot import get_config, authorize_chat
from dashboard.api_utils import WARROOMS_DIR, AGENTS_DIR, PROJECT_ROOT, build_skills_list, read_channel, read_room
from dashboard.telegram_sessions import get_session, clear_session, set_plan, set_mode

# Try to import plan_agent, handle graceful fallback if deepagents not available
try:
    from dashboard.plan_agent import refine_plan, summarize_plan
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False


logger = logging.getLogger(__name__)

async def handle_message(message: dict, bot_token: str):
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    if not chat_id or not text:
        return

    config = get_config()
    authorized_chats = config.get("authorized_chats", [])
    pairing_code = config.get("pairing_code")

    # Handle DM Pairing
    if str(chat_id) not in authorized_chats:
        if text.startswith("/pair"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1 and parts[1] == pairing_code:
                authorize_chat(chat_id)
                await send_reply(bot_token, chat_id, "✅ *Pairing successful!* You are now authorized to use OS Twin commands.")
            else:
                await send_reply(bot_token, chat_id, "❌ *Unauthorized.* Invalid pairing code.")
        else:
            await send_reply(bot_token, chat_id, f"🔒 *Unauthorized.* This bot is private. Please use `/pair <code>` to authorize this chat.")
        return

    # Authorized commands
    session = get_session(chat_id)

    if text.startswith("/menu"):
        await _cmd_menu(bot_token, chat_id)
    elif text.startswith("/draft"):
        await _cmd_draft(bot_token, chat_id, text)
    elif text.startswith("/edit"):
        await _cmd_edit_menu(bot_token, chat_id)
    elif text.startswith("/startplan"):
        await _cmd_startplan_menu(bot_token, chat_id)
    elif text.startswith("/viewplan"):
        await _cmd_viewplan_menu(bot_token, chat_id)
    elif text.startswith("/cancel"):
        clear_session(chat_id)
        await send_reply(bot_token, chat_id, "🛑 Action cancelled. Session cleared.")
    elif text.startswith("/dashboard"):
        await send_reply(bot_token, chat_id, _cmd_dashboard())
    elif text.startswith("/status"):
        await send_reply(bot_token, chat_id, _cmd_status())
    elif text.startswith("/compact"):
        await send_reply(bot_token, chat_id, _cmd_compact())
    elif text.startswith("/plans"):
        await send_reply(bot_token, chat_id, _cmd_plans())
    elif text.startswith("/errors"):
        await send_reply(bot_token, chat_id, _cmd_errors())
    elif text.startswith("/skills"):
        await send_reply(bot_token, chat_id, _cmd_skills())
    elif text.startswith("/usage"):
        await send_reply(bot_token, chat_id, _cmd_usage())
    elif text.startswith("/new"):
        await send_reply(bot_token, chat_id, _cmd_new())
    elif text.startswith("/restart"):
        await send_reply(bot_token, chat_id, "🔄 Restarting Command Center...")
        os.kill(os.getpid(), signal.SIGTERM)
    elif text.startswith("/help") or text.startswith("/start"):
        help_text = (
            "🤖 *OS Twin Command Center — Help Menu*\n"
            "`─────────────────────────────`\n\n"
            "✨ *Interactive AI Agent*\n"
            "🔸 `/menu` — Main interactive command menu.\n"
            "🔸 `/draft <idea>` — Create a new plan from a text prompt.\n"
            "🔸 `/edit` — Select a plan to edit and refine with AI.\n"
            "🔸 `/startplan` — Select and launch a plan.\n"
            "🔸 `/viewplan` — Select and read a plan.\n"
            "🔸 `/cancel` — Exit current editing/drafting session.\n\n"
            "📊 *Monitoring & Insights*\n"
            "🔸 `/dashboard` — Visual UI with real-time progress bars.\n"
            "🔸 `/status` — Detailed breakdown of every active War-Room.\n"
            "🔸 `/compact` — Sneak peek at the latest messages from agents.\n"
            "🔸 `/errors` — Extracts the root cause of any failed War-Rooms.\n\n"
            "📂 *Project & AI Resources*\n"
            "🔸 `/plans` — List all project Plans and their current status.\n"
            "🔸 `/skills` — View the library of tools the AI is permitted to use.\n"
            "🔸 `/usage` — Get a highly accurate Token consumption report.\n\n"
            "⚙️ *System Operations*\n"
            "🔸 `/new` — Wipe old War-Room data safely to start fresh.\n"
            "🔸 `/restart` — Reboot the Command Center background process.\n"
            "🔸 `/pair <code>` — Authorize a new chat to control the server.\n"
        )
        await send_reply(bot_token, chat_id, help_text)
    else:
        if text.startswith("/"):
            await send_reply(bot_token, chat_id, "⚠️ Unknown command. Type /help for a list of commands.")
        elif session.mode in ["drafting", "editing", "awaiting_idea"]:
            await _handle_stateful_text(bot_token, chat_id, text, session)

async def send_reply(bot_token: str, chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload)
        except Exception as e:
            logger.error(f"Failed to send Telegram reply: {e}")

async def send_document(bot_token: str, chat_id: int, file_path: Path, caption: str = ""):
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
    with open(file_path, "rb") as f:
        files = {"document": (file_path.name, f)}
        async with httpx.AsyncClient() as client:
            try:
                await client.post(url, data=data, files=files)
            except Exception as e:
                logger.error(f"Failed to send Telegram document: {e}")

async def send_inline_keyboard(bot_token: str, chat_id: int, text: str, keyboard: list):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": keyboard}
    }
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload)
        except Exception as e:
            logger.error(f"Failed to send Telegram inline keyboard: {e}")

async def answer_callback_query(bot_token: str, callback_query_id: str, text: str = None):
    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload)
        except Exception as e:
            logger.error(f"Failed to answer callback query: {e}")

async def handle_callback_query(update: dict, bot_token: str):
    callback_query = update.get("callback_query", {})
    query_id = callback_query.get("id")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    data = callback_query.get("data", "")

    if not chat_id or not data:
        return

    config = get_config()
    authorized_chats = config.get("authorized_chats", [])

    if str(chat_id) not in authorized_chats:
        await answer_callback_query(bot_token, query_id, "Unauthorized.")
        return

    # Acknowledge immediately to stop loading spinner
    await answer_callback_query(bot_token, query_id)

    # Dispatch logic
    if data == "menu:plans":
        await send_reply(bot_token, chat_id, _cmd_plans())
    elif data == "menu:cat:monitoring":
        await _cmd_submenu_monitoring(bot_token, chat_id)
    elif data == "menu:cat:plans":
        await _cmd_submenu_plans(bot_token, chat_id)
    elif data == "menu:cat:system":
        await _cmd_submenu_system(bot_token, chat_id)
    elif data == "cmd:dashboard":
        await send_reply(bot_token, chat_id, _cmd_dashboard())
    elif data == "cmd:status":
        await send_reply(bot_token, chat_id, _cmd_status())
    elif data == "cmd:compact":
        await send_reply(bot_token, chat_id, _cmd_compact())
    elif data == "cmd:errors":
        await send_reply(bot_token, chat_id, _cmd_errors())
    elif data == "cmd:draft_prompt":
        await send_reply(bot_token, chat_id, "✨ Send `/draft <your idea>` to create a new plan.")
    elif data == "cmd:viewplan":
        await _cmd_viewplan_menu(bot_token, chat_id)
    elif data == "cmd:edit":
        await _cmd_edit_menu(bot_token, chat_id)
    elif data == "cmd:startplan":
        await _cmd_startplan_menu(bot_token, chat_id)
    elif data == "cmd:new":
        await send_reply(bot_token, chat_id, _cmd_new())
    elif data == "cmd:restart":
        await send_reply(bot_token, chat_id, "🔄 Restarting...")
        os.kill(os.getpid(), signal.SIGTERM)
    elif data == "cmd:usage":
        await send_reply(bot_token, chat_id, _cmd_usage())
    elif data == "cmd:skills":
        await send_reply(bot_token, chat_id, _cmd_skills())
    elif data.startswith("menu:view:"):
        plan_id = data.split(":", 2)[2]
        await _view_plan(bot_token, chat_id, plan_id)
    elif data.startswith("menu:edit:"):
        plan_id = data.split(":", 2)[2]
        await _start_editing(bot_token, chat_id, plan_id)
    elif data.startswith("menu:launch_prompt:"):
        plan_id = data.split(":", 2)[2]
        await _prompt_launch(bot_token, chat_id, plan_id)
    elif data.startswith("menu:launch_confirm:"):
        plan_id = data.split(":", 2)[2]
        await _launch_plan(bot_token, chat_id, plan_id)
    elif data == "menu:launch_cancel":
        await send_reply(bot_token, chat_id, "🛑 Launch cancelled.")
    elif data == "menu:main":
        await _cmd_menu(bot_token, chat_id)

# --- Interactive Commands & Stateful AI Handlers ---

async def _cmd_menu(bot_token: str, chat_id: int):
    keyboard = [
        [{"text": "📊 Monitoring", "callback_data": "menu:cat:monitoring"}],
        [{"text": "📝 Plans & AI", "callback_data": "menu:cat:plans"}],
        [{"text": "⚙️ System", "callback_data": "menu:cat:system"}],
    ]
    await send_inline_keyboard(
        bot_token, chat_id,
        "🏢 *Main Control Center*\nSelect a category:",
        keyboard
    )

async def _cmd_submenu_monitoring(bot_token: str, chat_id: int):
    keyboard = [
        [{"text": "📊 Dashboard", "callback_data": "cmd:dashboard"}],
        [{"text": "💻 Status", "callback_data": "cmd:status"}],
        [{"text": "💬 Compact View", "callback_data": "cmd:compact"}],
        [{"text": "⚠️ Errors", "callback_data": "cmd:errors"}],
        [{"text": "⬅️ Back", "callback_data": "menu:main"}],
    ]
    await send_inline_keyboard(bot_token, chat_id,
        "📊 *Monitoring*\nReal-time War-Room insights:", keyboard)

async def _cmd_submenu_plans(bot_token: str, chat_id: int):
    keyboard = [
        [{"text": "✨ Draft New Plan", "callback_data": "cmd:draft_prompt"}],
        [{"text": "👁 View Plan", "callback_data": "cmd:viewplan"}],
        [{"text": "✏️ Edit Plan", "callback_data": "cmd:edit"}],
        [{"text": "🚀 Launch Plan", "callback_data": "cmd:startplan"}],
        [{"text": "📂 All Plans", "callback_data": "menu:plans"}],
        [{"text": "⬅️ Back", "callback_data": "menu:main"}],
    ]
    await send_inline_keyboard(bot_token, chat_id,
        "📝 *Plans & AI*\nDraft, view, edit, and launch plans:", keyboard)

async def _cmd_submenu_system(bot_token: str, chat_id: int):
    keyboard = [
        [{"text": "🧹 Clean War-Rooms", "callback_data": "cmd:new"}],
        [{"text": "🔄 Restart", "callback_data": "cmd:restart"}],
        [{"text": "📈 Token Usage", "callback_data": "cmd:usage"}],
        [{"text": "🧠 Skills", "callback_data": "cmd:skills"}],
        [{"text": "⬅️ Back", "callback_data": "menu:main"}],
    ]
    await send_inline_keyboard(bot_token, chat_id,
        "⚙️ *System*\nSystem operations & resources:", keyboard)

def _get_available_plans() -> list:
    plans_dir = AGENTS_DIR / "plans"
    if not plans_dir.exists():
        return []
    plans = []
    for f in sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.stem == "PLAN.template" or f.name.endswith(".refined.md"):
            continue
        try:
            content = f.read_text()
            title_match = re.search(r"^# Plan:\s*(.+)", content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else f.stem
            if len(title) > 25:
                title = title[:22] + "..."
            date_str = datetime.fromtimestamp(f.stat().st_mtime).strftime("%b %d")
            plans.append({"id": f.stem, "label": f"{title} ({date_str})"})
        except Exception:
            plans.append({"id": f.stem, "label": f"{f.stem}"})
    return plans

def _build_plan_keyboard(plans: list, prefix: str) -> list:
    keyboard = []
    for plan in plans[:10]: # Limit to 10 for inline keyboard limits
        keyboard.append([{"text": f"📄 {plan['label']}", "callback_data": f"{prefix}:{plan['id']}"}])
    return keyboard

async def _cmd_startplan_menu(bot_token: str, chat_id: int):
    plans = _get_available_plans()
    if not plans:
        await send_reply(bot_token, chat_id, "ℹ️ No plans found. Use `/draft <idea>` to create one.")
        return
    keyboard = _build_plan_keyboard(plans, "menu:launch_prompt")
    await send_inline_keyboard(bot_token, chat_id, "🚀 *Select a Plan to Launch:*", keyboard)

async def _cmd_edit_menu(bot_token: str, chat_id: int):
    plans = _get_available_plans()
    if not plans:
        await send_reply(bot_token, chat_id, "ℹ️ No plans found. Use `/draft <idea>` to create one.")
        return
    keyboard = _build_plan_keyboard(plans, "menu:edit")
    await send_inline_keyboard(bot_token, chat_id, "✏️ *Select a Plan to Edit:*", keyboard)

async def _cmd_viewplan_menu(bot_token: str, chat_id: int):
    plans = _get_available_plans()
    if not plans:
        await send_reply(bot_token, chat_id, "ℹ️ No plans found.")
        return
    keyboard = _build_plan_keyboard(plans, "menu:view")
    await send_inline_keyboard(bot_token, chat_id, "👁 *Select a Plan to View:*", keyboard)

async def _view_plan(bot_token: str, chat_id: int, plan_id: str):
    plan_file = AGENTS_DIR / "plans" / f"{plan_id}.md"
    if not plan_file.exists():
        await send_reply(bot_token, chat_id, f"❌ Plan `{plan_id}` not found.")
        return
    content = plan_file.read_text()
    if len(content) > 3500:
        content = content[:3500] + "\n...[truncated]"
    await send_reply(bot_token, chat_id, f"📄 *Plan: {plan_id}*\n```markdown\n{content}\n```")

async def _start_editing(bot_token: str, chat_id: int, plan_id: str):
    plan_file = AGENTS_DIR / "plans" / f"{plan_id}.md"
    if not plan_file.exists():
        await send_reply(bot_token, chat_id, f"❌ Plan `{plan_id}` not found.")
        return
    set_plan(chat_id, plan_id)
    set_mode(chat_id, "editing")
    await send_reply(bot_token, chat_id, f"✏️ *Editing Mode Active for `{plan_id}`*\n\nSend instructions to the AI to refine this plan. (e.g. 'Add a new epic for user authentication'). Type /cancel to stop editing.")

async def _cmd_draft(bot_token: str, chat_id: int, text: str):
    if not AI_AVAILABLE:
        await send_reply(bot_token, chat_id, "⚠️ AI features are not available because `deepagents` or API keys are not configured.")
        return

    idea = text[len("/draft"):].strip()
    
    # If no idea is provided, prompt the user for one and set a special "awaiting_idea" mode
    if not idea:
        set_plan(chat_id, "new")  # dummy plan id
        set_mode(chat_id, "awaiting_idea")
        await send_reply(bot_token, chat_id, "✨ What's your idea? Send me a message describing what you want to build:")
        return

    await _process_draft(bot_token, chat_id, idea)

import re

def _generate_plan_id(idea: str) -> str:
    """Generate a human-readable plan ID from the user's idea."""
    # Clean the string: remove non-alphanumeric, convert to lowercase
    clean_idea = re.sub(r'[^a-zA-Z0-9\s]', '', idea).lower()
    words = clean_idea.split()
    
    # Common filler words to ignore for a cleaner slug
    stop_words = {"a", "an", "the", "build", "create", "make", "write", "i", "want", "to", "for", "of", "some"}
    
    # Filter words
    meaningful_words = [w for w in words if w not in stop_words]
    
    # Use up to 3 meaningful words, or fallback to first 3 words if all were filtered
    slug_words = meaningful_words[:3] if meaningful_words else words[:3]
    slug = "-".join(slug_words)
    
    # Generate a short 4-char hash for uniqueness
    short_hash = uuid.uuid4().hex[:4]
    
    if not slug:
        return f"plan-{short_hash}"
    return f"{slug}-{short_hash}"

async def _process_draft(bot_token: str, chat_id: int, idea: str):
    plan_id = _generate_plan_id(idea)
    set_plan(chat_id, plan_id)
    set_mode(chat_id, "drafting")

    await send_reply(bot_token, chat_id, f"⏳ *Drafting Plan...*\nIdea: `{idea}`\nPlease wait while the AI generates the initial plan.")
    
    try:
        plans_dir = AGENTS_DIR / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        
        result = await refine_plan(
            user_message=f"Draft a new plan for: {idea}",
            plans_dir=plans_dir
        )
        
        if isinstance(result, dict):
            plan_text = result.get("plan", result.get("full_response", ""))
            # If the parser couldn't find a clean plan section, fallback
            if not plan_text: plan_text = result.get("full_response", "")
        else:
            plan_text = result
            
        plan_file = plans_dir / f"{plan_id}.md"
        plan_file.write_text(plan_text)
        
        # Keep in drafting mode so they can refine it
        set_mode(chat_id, "editing") 
        
        await send_reply(bot_token, chat_id, f"✅ *Plan Drafted:* `{plan_id}`\n\nYou are now in editing mode. Send further instructions to refine it, or /cancel to exit.")
        
        # Send the markdown file as a document
        await send_document(bot_token, chat_id, plan_file, caption=f"📄 Plan `{plan_id}` File")

        # Generate and send summary
        await send_reply(bot_token, chat_id, "⏳ *Generating Plan Summary...*")
        summary = await summarize_plan(plan_text, plans_dir=plans_dir)
        await send_reply(bot_token, chat_id, f"📝 *Plan Summary:*\n\n{summary}")
        
    except Exception as e:
        logger.error(f"Error drafting plan: {e}")
        clear_session(chat_id)
        await send_reply(bot_token, chat_id, f"❌ Failed to draft plan: {e}")

async def _handle_stateful_text(bot_token: str, chat_id: int, text: str, session):
    if not AI_AVAILABLE:
        await send_reply(bot_token, chat_id, "⚠️ AI features are not available.")
        clear_session(chat_id)
        return

    if session.mode == "awaiting_idea":
        await _process_draft(bot_token, chat_id, text)
        return

    plan_id = session.active_plan_id
    if not plan_id:
        clear_session(chat_id)
        return
        
    plan_file = AGENTS_DIR / "plans" / f"{plan_id}.md"
    current_content = plan_file.read_text() if plan_file.exists() else ""
    
    await send_reply(bot_token, chat_id, f"⏳ *Refining `{plan_id}`...*")
    
    try:
        plans_dir = AGENTS_DIR / "plans"
        
        # Add to chat history
        session.chat_history.append({"role": "user", "content": text})
        
        result = await refine_plan(
            user_message=text,
            plan_content=current_content,
            chat_history=session.chat_history[:-1], # all but current
            plans_dir=plans_dir
        )
        
        if isinstance(result, dict):
            plan_text = result.get("plan", result.get("full_response", ""))
            if not plan_text: plan_text = result.get("full_response", "")
        else:
            plan_text = result
            
        plan_file.write_text(plan_text)
        session.chat_history.append({"role": "assistant", "content": "I have updated the plan as requested."})

        await send_reply(bot_token, chat_id, f"✅ *Plan Updated:* `{plan_id}`")

        # Send the updated markdown file as a document
        await send_document(bot_token, chat_id, plan_file, caption=f"📄 Updated Plan `{plan_id}`")

        # Generate and send summary of changes
        await send_reply(bot_token, chat_id, "⏳ *Generating Update Summary...*")
        summary = await summarize_plan(plan_text, plans_dir=plans_dir)
        await send_reply(bot_token, chat_id, f"📝 *Plan Summary (Post-Update):*\n\n{summary}\n\n_(Send more instructions to keep editing, or /cancel to exit)_")
    except Exception as e:
        logger.error(f"Error refining plan: {e}")
        await send_reply(bot_token, chat_id, f"❌ Failed to refine plan: {e}")

async def _prompt_launch(bot_token: str, chat_id: int, plan_id: str):
    keyboard = [
        [{"text": "🚀 Launch", "callback_data": f"menu:launch_confirm:{plan_id}"}],
        [{"text": "❌ Cancel", "callback_data": "menu:launch_cancel"}]
    ]
    await send_inline_keyboard(bot_token, chat_id, f"⚠️ *Confirm Launch*\nAre you sure you want to launch `{plan_id}`? This will wipe the current war-rooms.", keyboard)

async def _launch_plan(bot_token: str, chat_id: int, plan_id: str):
    plan_file = AGENTS_DIR / "plans" / f"{plan_id}.md"
    if not plan_file.exists():
        await send_reply(bot_token, chat_id, f"❌ Plan `{plan_id}` not found.")
        return
        
    run_sh = AGENTS_DIR / "run.sh"
    if not run_sh.exists():
        await send_reply(bot_token, chat_id, "❌ `run.sh` not found. Cannot launch plan.")
        return

    import re
    # Extract title from plan content
    plan_content = plan_file.read_text()
    title_match = re.search(r"^# Plan:\s*(.+)", plan_content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else plan_id

    # Extract working_dir from plan content (## Config section)
    wd_match = re.search(r"working_dir:\s*(.+)", plan_content)
    extracted_wd = wd_match.group(1).strip() if wd_match else str(PROJECT_ROOT)
    
    # Resolve absolute working directory
    working_dir = extracted_wd
    if not Path(working_dir).is_absolute():
        working_dir = str(PROJECT_ROOT / working_dir)
        
    # Ensure it exists
    if not Path(working_dir).exists():
        try:
            Path(working_dir).mkdir(parents=True, exist_ok=True)
        except Exception:
            working_dir = str(PROJECT_ROOT)

    # Use the same warrooms logic as Web UI
    warrooms_dir = str(Path(working_dir) / ".war-rooms")
    
    # Wipe old war-rooms
    warrooms_path = Path(warrooms_dir)
    if warrooms_path.exists():
        import shutil
        try:
            shutil.rmtree(warrooms_path)
            warrooms_path.mkdir()
        except Exception as e:
            await send_reply(bot_token, chat_id, f"⚠️ Failed to wipe old war-rooms: {e}")

    # Write .meta.json with status: launched, explicitly matching Web UI structure
    meta_path = AGENTS_DIR / "plans" / f"{plan_id}.meta.json"
    existing_meta = {}
    if meta_path.exists():
        try:
            existing_meta = json.loads(meta_path.read_text())
        except:
            pass
            
    meta = {
        **existing_meta,
        "plan_id": plan_id,
        "title": title,
        "working_dir": extracted_wd,
        "warrooms_dir": warrooms_dir,
        "status": "launched",
    }
    if "created_at" not in meta:
        meta["created_at"] = datetime.now(timezone.utc).isoformat()
    meta["launched_at"] = datetime.now(timezone.utc).isoformat()

    meta_path.write_text(json.dumps(meta, indent=2))
    
    # Sync with zvec store if available (Crucial for Dashboard UI)
    store = global_state.store
    if store:
        try:
            from dashboard.zvec_store import OSTwinStore
            epics = OSTwinStore._parse_plan_epics(plan_content, plan_id)
            now = datetime.now(timezone.utc).isoformat()
            store.index_plan(
                plan_id=plan_id, title=title, content=plan_content,
                epic_count=len(epics), filename=plan_file.name,
                status="launched", created_at=now,
            )
            for epic in epics:
                store.index_epic(
                    epic_ref=epic["task_ref"], plan_id=plan_id,
                    title=epic["title"], body=epic["body"],
                    room_id=epic["room_id"],
                    working_dir=epic.get("working_dir", "."),
                    status="pending",
                )
        except Exception as e:
            logger.error(f"zvec: plan indexing failed ({e})")

    # Prepare environment for run.sh to enforce correct working directory
    import os
    env = os.environ.copy()
    env["PROJECT_DIR"] = working_dir

    # Launch in background
    import subprocess
    try:
        logger.info(f"Telegram Launch: {run_sh} {plan_file} at {working_dir}")
        subprocess.Popen(
            [str(run_sh), str(plan_file)],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env
        )
        
        await send_reply(bot_token, chat_id, f"🚀 *Plan Launched!* `{plan_id}`\n\nUse /dashboard or /status to monitor progress.")
    except Exception as e:
        logger.error(f"Failed to launch plan: {e}")
        await send_reply(bot_token, chat_id, f"❌ Failed to launch plan: {e}")

# --- Command Implementations ---

def _cmd_dashboard() -> str:
    # A text-based visual representation of the dashboard with progress bars
    total_rooms = 0
    active_rooms = 0
    passed_rooms = 0
    failed_rooms = 0
    if WARROOMS_DIR.exists():
        for d in WARROOMS_DIR.glob("room-*"):
            if not d.is_dir(): continue
            total_rooms += 1
            st = read_room(d).get("status", "unknown")
            if st in ["running", "pending", "review"]: active_rooms += 1
            elif st == "passed": passed_rooms += 1
            elif "fail" in st: failed_rooms += 1

    # Helper to generate progress bars
    def make_bar(count, total, length=12):
        if total == 0: return "░" * length
        filled = int(round((count / total) * length))
        return "█" * filled + "░" * (length - filled)

    pct_pass = (passed_rooms / total_rooms * 100) if total_rooms else 0
    pct_fail = (failed_rooms / total_rooms * 100) if total_rooms else 0
    pct_act = (active_rooms / total_rooms * 100) if total_rooms else 0

    bar_pass = make_bar(passed_rooms, total_rooms)
    bar_fail = make_bar(failed_rooms, total_rooms)
    bar_act  = make_bar(active_rooms, total_rooms)

    art = f"""🎛 *OS TWIN COMMAND CENTER* 🎛
_System Status:_ 🟢 *ONLINE*

📊 *WAR-ROOMS OVERVIEW*
`─────────────────────────────`
🏃‍♂️ *Active:*   `{active_rooms:<4}`
✅ *Passed:*   `{passed_rooms:<4}`
❌ *Failed:*   `{failed_rooms:<4}`
📦 *Total:*    `{total_rooms:<4}`
`─────────────────────────────`

📈 *EXECUTION PROGRESS*
✅ `Passed:` `{bar_pass}` `{pct_pass:>5.1f}%`
❌ `Failed:` `{bar_fail}` `{pct_fail:>5.1f}%`
🏃‍♂️ `Active:` `{bar_act}` `{pct_act:>5.1f}%`

🔗 [Open Web Dashboard](http://localhost:9000)
"""
    return art

def _cmd_status() -> str:
    if not WARROOMS_DIR.exists():
        return "ℹ️ No War-Rooms found."
    lines = ["📋 *War-Rooms Status:*", "`─────────────────────────────`"]
    
    status_emoji = {
        "passed": "✅",
        "running": "🏃‍♂️",
        "pending": "⏳",
        "review": "👀",
        "failed-final": "❌",
        "unknown": "❓"
    }
    
    for d in sorted(WARROOMS_DIR.glob("room-*")):
        if d.is_dir():
            room = read_room(d)
            st = room.get("status", "unknown")
            emoji = status_emoji.get(st, "⚠️") if "fail" not in st else "❌"
            msgs = room.get('message_count', 0)
            lines.append(f"{emoji} `{room['room_id']}` : {st.upper()} `[{msgs} msgs]`")
            
    if len(lines) == 2:
        return "ℹ️ No War-Rooms found."
    lines.append("`─────────────────────────────`")
    return "\n".join(lines)

def _cmd_compact() -> str:
    if not WARROOMS_DIR.exists():
        return "ℹ️ No active agents."
    lines = ["💬 *Latest Agent Messages:*"]
    for d in sorted(WARROOMS_DIR.glob("room-*")):
        if not d.is_dir(): continue
        room = read_room(d)
        if room["status"] in ["passed", "failed-final"]:
            continue # Skip inactive
        msgs = read_channel(d, limit=1)
        if msgs:
            msg = msgs[0]
            # Strip markdown to prevent 400 errors from Telegram API
            body = msg.get('body', '')[:100].replace('\n', ' ')
            body = body.replace('*', '').replace('_', '').replace('`', "'")
            lines.append(f"*{d.name}* ({msg.get('from', 'Unknown')}): `{body}...`")
    if len(lines) == 1:
        return "ℹ️ No active agents right now."
    return "\n".join(lines)

def _cmd_plans() -> str:
    if not global_state.store:
        return "⚠️ Store not initialized."
    plans = global_state.store.get_all_plans()
    if not plans:
        return "ℹ️ No plans found."
    lines = ["📂 *Project Plans:*"]
    for p in plans:
        title = p.get('title', 'Untitled')
        if len(title) > 40:
             title = title[:37] + "..."
        lines.append(f"• *{title}* ({p.get('status', 'unknown')})\n  └ `ID: {p['plan_id']}`")
    return "\n".join(lines)

def _cmd_errors() -> str:
    if not WARROOMS_DIR.exists():
        return "✅ System is stable. No errors."
    errors = []
    for d in sorted(WARROOMS_DIR.glob("room-*")):
        if not d.is_dir(): continue
        room = read_room(d)
        if "fail" in room["status"]:
            errors.append(f"⚠️ *{d.name}* is {room['status'].upper()}")
            # Get last message to see why
            msgs = read_channel(d, limit=3)
            for m in reversed(msgs):
                if m.get("type") in ["fail", "error"]:
                    body = m.get('body', '')[:150].replace('\n', ' ')
                    body = body.replace('*', '').replace('_', '').replace('`', "'")
                    errors.append(f"  └ ❌ `{body}...`")
                    break
    if not errors:
        return "✅ System is stable. No active errors."
    return "\n".join(errors)

def _cmd_skills() -> str:
    skills = build_skills_list(limit=50)
    if not skills:
        return "ℹ️ No skills installed."
    lines = ["🧠 *Available Skills:*"]
    for s in skills:
        tags = ", ".join(s.tags) if s.tags else "General"
        lines.append(f"• `{s.name}`: [{tags}]")
    return "\n".join(lines)

def _cmd_usage() -> str:
    total_tokens = 0
    total_budget = 0
    room_count = 0
    
    # Try to use tiktoken for accurate counting (standard for GPT-based models)
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        def count_tokens(text):
            return len(encoding.encode(text))
    except ImportError:
        # Fallback to precise 4-char heuristic if tiktoken is missing
        def count_tokens(text):
            return len(text) // 4

    if WARROOMS_DIR.exists():
        # Read exact messages from channel files to count tokens
        for channel_file in WARROOMS_DIR.glob("room-*/channel.jsonl"):
            try:
                content = channel_file.read_text()
                total_tokens += count_tokens(content)
                room_count += 1
            except: continue
            
        # Get exact budget from config files
        for config_file in WARROOMS_DIR.glob("room-*/config.json"):
            try:
                conf = json.loads(config_file.read_text())
                total_budget += conf.get("budget_tokens_max", 500000)
            except: continue

    # Format numbers
    def fmt(n):
        if n >= 1000000: return f"{n/1000000:.1f}M"
        if n >= 1000: return f"{n/1000:.1f}k"
        return str(n)

    pct = (total_tokens / total_budget * 100) if total_budget else 0
    
    # Helper to generate progress bars
    def make_bar(count, total, length=12):
        if total == 0: return "░" * length
        filled = min(length, int(round((count / total) * length)))
        return "█" * filled + "░" * (length - filled)

    bar = make_bar(total_tokens, total_budget, length=15)
    
    res = f"""📈 *TOKEN USAGE REPORT*
`─────────────────────────────`
🧮 *Exact Tokens Used:* `{fmt(total_tokens)}`
💰 *Total Budget:*      `{fmt(total_budget)}`
📊 *Usage Rate:*        `{pct:.1f}%`
📦 *Active Rooms:*      `{room_count}`
`─────────────────────────────`
🚦 `Capacity:` `{bar}`
_Note: Tokens calculated precisely via cl100k-base tokenizer._
"""
    return res

def _cmd_new() -> str:
    import shutil
    if WARROOMS_DIR.exists():
        try:
            shutil.rmtree(WARROOMS_DIR)
            WARROOMS_DIR.mkdir()
            return "🧹 *Cleaned up all War-Rooms data.* Ready for a new Plan."
        except Exception as e:
            return f"❌ *Failed to clean War-Rooms:* {e}"
    return "ℹ️ No War-Rooms to clean."

# --- Main Polling Loop ---

async def register_commands(bot_token: str):
    url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"
    commands = [
        {"command": "menu", "description": "🏢 Main Control Center"},
        {"command": "dashboard", "description": "📊 Real-time War-Room progress"},
        {"command": "draft", "description": "📝 Draft a new Plan with AI"},
        {"command": "status", "description": "💻 List running War-Rooms"},
        {"command": "help", "description": "❓ Detailed user guide"},
    ]
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json={"commands": commands})
        except Exception as e:
            logger.error(f"Failed to register bot commands: {e}")

async def start_polling():
    print(">>> TELEGRAM POLLER TASK INITIATED <<<")
    logger.info("Starting Telegram Bot Poller...")
    offset = 0
    while True:
        try:
            config = get_config()
            bot_token = config.get("bot_token")
            if not bot_token or bot_token == "test_token":
                print(">>> TELEGRAM POLLER: No token found. Waiting... <<<")
                await asyncio.sleep(10) # check every 10s if config is updated
                continue
            
            # Register commands on startup
            if offset == 0:
                await register_commands(bot_token)
            
            print(f">>> TELEGRAM POLLER: Polling with token {bot_token[:10]}... <<<")
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={"offset": offset, "timeout": 20}, timeout=25.0)
                if response.status_code == 200:
                    data = response.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        if "message" in update:
                            await handle_message(update["message"], bot_token)
                        elif "callback_query" in update:
                            await handle_callback_query(update, bot_token)
                else:
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Telegram Polling Error: {e}")
            await asyncio.sleep(5)
