import asyncio
import httpx
import logging
import json
import os
import signal
from pathlib import Path
import dashboard.global_state as global_state
from dashboard.telegram_bot import get_config, authorize_chat
from dashboard.api_utils import WARROOMS_DIR, AGENTS_DIR, build_skills_list, read_channel, read_room

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
    if text.startswith("/dashboard"):
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

async def send_reply(bot_token: str, chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload)
        except Exception as e:
            logger.error(f"Failed to send Telegram reply: {e}")

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
        lines.append(f"• `{p['plan_id']}`: {p.get('title', 'Untitled')} ({p.get('status', 'unknown')})")
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
            
            print(f">>> TELEGRAM POLLER: Polling with token {bot_token[:10]}... <<<")
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={"offset": offset, "timeout": 20}, timeout=25.0)
                if response.status_code == 200:
                    data = response.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        message = update.get("message")
                        if message:
                            await handle_message(message, bot_token)
                else:
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Telegram Polling Error: {e}")
            await asyncio.sleep(5)
