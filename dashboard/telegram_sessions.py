import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class UserSession:
    chat_id: int
    active_plan_id: Optional[str] = None
    mode: str = "idle"  # "idle", "editing", "drafting"
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    last_activity: float = field(default_factory=time.time)

# In-memory session store: chat_id -> UserSession
_sessions: Dict[int, UserSession] = {}

SESSION_TIMEOUT_SECONDS = 30 * 60  # 30 minutes

def get_session(chat_id: int) -> UserSession:
    """Get or create a session for the given chat_id, handling timeouts."""
    now = time.time()
    session = _sessions.get(chat_id)
    
    if session:
        # Check timeout
        if now - session.last_activity > SESSION_TIMEOUT_SECONDS:
            session = UserSession(chat_id=chat_id)
            _sessions[chat_id] = session
        else:
            session.last_activity = now
    else:
        session = UserSession(chat_id=chat_id)
        _sessions[chat_id] = session
        
    return session

def clear_session(chat_id: int) -> None:
    """Reset the session for the given chat_id."""
    if chat_id in _sessions:
        _sessions[chat_id] = UserSession(chat_id=chat_id)

def set_plan(chat_id: int, plan_id: str) -> None:
    """Set the active plan for a session."""
    session = get_session(chat_id)
    session.active_plan_id = plan_id
    session.last_activity = time.time()

def set_mode(chat_id: int, mode: str) -> None:
    """Set the interaction mode for a session."""
    session = get_session(chat_id)
    session.mode = mode
    session.last_activity = time.time()
