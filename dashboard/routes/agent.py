import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from dashboard.agent_bridge import ask_agent
from dashboard.auth import get_current_user

router = APIRouter(prefix="/api/agent", tags=["agent"])
logger = logging.getLogger(__name__)

class AgentAskRequest(BaseModel):
    question: str
    platform: Optional[str] = "generic"

@router.post("/ask")
async def agent_ask(request: AgentAskRequest, user: dict = Depends(get_current_user)):
    """Ask the Ostwin AI Agent a question about the project."""
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    try:
        answer = await ask_agent(request.question, platform=request.platform)
        return {"answer": answer}
    except Exception as e:
        logger.error(f"Error in agent_ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))
