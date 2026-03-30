from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class NotificationFormatter:
    """Base notification formatter. Subclass per platform to override markup methods.

    Uses Template Method pattern: format() dispatches to _fmt_* methods which
    call markup hooks (bold, code, escape, etc.) that subclasses override.
    """

    # -- Markup hooks (override per platform) --

    def bold(self, text: str) -> str:
        return str(text)

    def italic(self, text: str) -> str:
        return str(text)

    def code(self, text: str) -> str:
        return str(text)

    def code_block(self, text: str, lang: str = "") -> str:
        return str(text)

    def link(self, text: str, url: str) -> str:
        return f"{text} ({url})"

    def quote(self, text: str) -> str:
        return text

    def separator(self) -> str:
        return "━━━━━━━━━━━━━━━"

    def escape(self, text: str) -> str:
        return str(text)

    # -- Shared helpers --

    def truncate(self, text: str, limit: int = 200) -> str:
        if len(text) > limit:
            return text[:limit] + "..."
        return text

    def progress_bar(self, done: int, total: int) -> str:
        pct = int(done / total * 100) if total else 0
        filled = pct // 10
        bar = "▓" * filled + "░" * (10 - filled)
        return f"{bar} {pct}% ({done}/{total})"

    def type_icon(self, msg_type: str) -> str:
        icons = {"status-update": "📋", "code-output": "🔧", "done": "✅", "fail": "❌", "fix": "🔧"}
        return icons.get(msg_type, "💬")

    def extract_objective(self, desc: str, task_ref: str) -> str:
        lines = [line.strip() for line in desc.split("\n") if line.strip()] if desc else []
        for line in lines:
            clean = line.lstrip("# ").strip()
            if clean.lower().startswith("objective:"):
                return clean[len("objective:"):].strip()
            if task_ref and not clean.startswith(task_ref) and len(clean) > 10:
                return clean
            if not task_ref and len(clean) > 10:
                return clean
        return ""

    # -- Public API --

    def format(self, event_type: str, data: Dict[str, Any]) -> str:
        formatter = getattr(self, f"_fmt_{event_type}", None)
        if formatter:
            return formatter(data)
        return f"ℹ️ {self.bold(self.escape(event_type.replace('_', ' ').title()))}"

    # -- Event formatters (Template Method) --

    def _fmt_room_created(self, data: Dict[str, Any]) -> str:
        room = data.get("room", {})
        room_id = room.get("room_id", "?")
        task_ref = room.get("task_ref", "")
        status = room.get("status", "pending")
        retries = room.get("retries", 0)
        msg_count = room.get("message_count", 0)
        goal_done = room.get("goal_done", 0)
        goal_total = room.get("goal_total", 0)
        desc = room.get("task_description", "")
        objective = self.extract_objective(desc, task_ref)

        msg = f"🆕 {self.bold('New Room Created')}\n"
        msg += f"{self.separator()}\n"
        msg += f"🏷 Room: {self.code(self.escape(room_id))}\n"
        if task_ref:
            msg += f"📌 Epic: {self.code(self.escape(task_ref))}\n"
        msg += f"📊 Status: {self.escape(status)}\n"
        if goal_total > 0:
            msg += f"🎯 Tasks: {goal_done}/{goal_total}\n"
        if msg_count > 0:
            msg += f"💬 Messages: {msg_count}\n"
        if retries > 0:
            msg += f"🔁 Retries: {retries}\n"
        if objective:
            msg += f"\n📝 {self.escape(self.truncate(objective, 300))}"
        return msg

    def _fmt_room_updated(self, data: Dict[str, Any]) -> str:
        room = data.get("room", {})
        room_id = room.get("room_id", "?")
        task_ref = room.get("task_ref", "")
        status = room.get("status", "")
        goal_done = room.get("goal_done", 0)
        goal_total = room.get("goal_total", 0)
        retries = room.get("retries", 0)
        new_messages = data.get("new_messages", [])

        msg = f"🔄 {self.bold('Room Updated')}\n"
        msg += f"{self.separator()}\n"
        msg += f"🏷 Room: {self.code(self.escape(room_id))}"
        if task_ref:
            msg += f" ({self.code(self.escape(task_ref))})"
        msg += "\n"
        msg += f"📊 Status: {self.escape(status)}\n"
        if goal_total > 0:
            msg += f"🎯 Progress: {self.progress_bar(goal_done, goal_total)}\n"
        if retries > 0:
            msg += f"🔁 Retries: {retries}\n"

        if new_messages:
            msg += f"\n📨 {self.bold(f'{len(new_messages)} new message(s):')}\n"
            for m in new_messages[-3:]:
                sender = m.get("from", "unknown")
                body = m.get("body", "")
                msg_type = m.get("type", "")
                icon = self.type_icon(msg_type)
                if body:
                    msg += f"{icon} {self.bold(self.escape(sender))}: {self.escape(self.truncate(body, 150))}\n"
        return msg

    def _fmt_room_removed(self, data: Dict[str, Any]) -> str:
        room_id = data.get("room_id", "?")
        return f"🗑 {self.bold('Room Removed')}\n🏷 Room: {self.code(self.escape(room_id))}"

    def _fmt_room_message(self, data: Dict[str, Any]) -> str:
        room_id = data.get("room_id", "?")
        message = data.get("message", {})
        sender = message.get("from", "")
        body = message.get("body", "")
        msg_type = message.get("type", "")
        to = message.get("to", "")

        type_label = msg_type.replace("-", " ").title() if msg_type else "Message"

        msg = f"💬 {self.bold(self.escape(type_label))} in {self.code(self.escape(room_id))}\n"
        msg += f"{self.separator()}\n"
        if sender:
            msg += f"👤 From: {self.escape(sender)}\n"
        if to:
            msg += f"➡️ To: {self.escape(to)}\n"
        if body:
            msg += f"\n{self.escape(self.truncate(body, 500))}"
        return msg

    def _fmt_plans_updated(self, data: Dict[str, Any]) -> str:
        return f"📋 {self.bold('Plans Updated')}\nPlan configuration has been modified."

    def _fmt_reaction_toggled(self, data: Dict[str, Any]) -> str:
        entity = data.get("entity_id", "?")
        user = data.get("user_id", "?")
        reaction = data.get("reaction_type", "")
        return f"👍 {self.bold('Reaction')} by {self.bold(self.escape(user))} on {self.code(self.escape(entity))}\nType: {self.escape(reaction)}"

    def _fmt_comment_published(self, data: Dict[str, Any]) -> str:
        entity = data.get("entity_id", "?")
        comment = data.get("comment", {})
        user = comment.get("user_id", "?") if isinstance(comment, dict) else "?"
        body = comment.get("body", "") if isinstance(comment, dict) else ""
        msg = f"💬 {self.bold('New Comment')} by {self.bold(self.escape(user))} on {self.code(self.escape(entity))}"
        if body:
            msg += f"\n\n{self.escape(self.truncate(body, 300))}"
        return msg


class BaseChatAdapter(ABC):
    """Abstract base for chat platform transport.

    Subclasses must implement send_message, handle_webhook, validate_config.
    Set formatter_class to a NotificationFormatter subclass for platform-specific formatting.
    """

    formatter_class: type = NotificationFormatter

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.formatter = self.formatter_class()

    @abstractmethod
    async def send_message(self, text: str, room_id: Optional[str] = None) -> bool:
        pass

    @abstractmethod
    async def handle_webhook(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, raw_body: Optional[bytes] = None) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        pass

    def format_notification(self, event_type: str, data: Dict[str, Any]) -> str:
        return self.formatter.format(event_type, data)
