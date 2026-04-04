import asyncio
import logging
from typing import Dict, Any, AsyncGenerator

from dashboard.conversation_store import conversation_store
from dashboard.global_state import broadcaster

logger = logging.getLogger(__name__)

class CommandDispatcher:
    def __init__(self):
        pass

    async def dispatch(self, command: str, conversation_id: str, append_user_message: bool = True) -> AsyncGenerator[str, None]:
        """
        Parses intent and yields markdown text chunks.
        Also broadcasts via WebSocket for realtime UI updates.
        """
        intent = self._parse_intent(command)
        
        # Append user message
        if append_user_message:
            conversation_store.append_message(conversation_id, "user", command)
        
        # We accumulate the full response to save at the end
        full_response = ""
        
        if intent == "create_plan":
            yield "I will help you create a plan. Let me generate that for you...\n\n"
            full_response += "I will help you create a plan. Let me generate that for you...\n\n"
            # Here we could call plan_agent
            from dashboard.plan_agent import refine_plan
            try:
                res = await refine_plan(user_message=command, plan_content="")
                content = res.get("full_response", "") if isinstance(res, dict) else res
                yield content
                full_response += content
            except Exception as e:
                err = f"Failed to generate plan: {e}"
                yield err
                full_response += err
                
        elif intent == "get_status":
            resp = "Here is the current system status:\n- All systems nominal.\n\n*Suggested follow-up:* `Refresh status`"
            yield resp
            full_response += resp
            
        elif intent == "connect_platform":
            resp = "Connecting to platform... Please see the Settings page for configuration.\n\n*Suggested follow-up:* `Open Settings`"
            yield resp
            full_response += resp
            
        else:
            # Fallback or generic agent
            response_text = f"I received your command: '{command}'. I am a mock response from the agent."
            for word in response_text.split(" "):
                yield word + " "
                full_response += word + " "
                await asyncio.sleep(0.05)
                
        # Append assistant message on completion
        conversation_store.append_message(conversation_id, "assistant", full_response)
        
        # Return structured response (but via stream, the caller can just yield it)

    def _parse_intent(self, command: str) -> str:
        cmd_lower = command.lower()
        if "plan" in cmd_lower or "create" in cmd_lower:
            return "create_plan"
        if "status" in cmd_lower:
            return "get_status"
        if "connect" in cmd_lower or "telegram" in cmd_lower:
            return "connect_platform"
        return "general"

dispatcher = CommandDispatcher()
