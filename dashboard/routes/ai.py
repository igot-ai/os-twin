"""AI Gateway routes — exposes shared/ai as HTTP for TypeScript callers.

Two endpoints on the existing dashboard (port 9000):
- ``POST /api/ai/complete`` — completion (prompt or multi-turn + tools)
- ``POST /api/ai/embed`` — embedding (cloud or local)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Ensure shared module is importable
_agents_dir = Path(__file__).resolve().parent.parent.parent / ".agents"
if str(_agents_dir) not in sys.path:
    sys.path.insert(0, str(_agents_dir))

router = APIRouter(prefix="/api/ai", tags=["ai"])


# ── Request / Response models ─────────────────────────────────────────────


class ToolCallModel(BaseModel):
    id: str
    function: Dict[str, str]


class CompleteRequest(BaseModel):
    prompt: Optional[str] = None
    messages: Optional[List[Dict[str, Any]]] = None
    model: Optional[str] = None
    purpose: Optional[str] = None
    system: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    response_format: Optional[Dict[str, Any]] = None
    max_tokens: int = 4096
    temperature: float = 0.0


class CompleteResponse(BaseModel):
    text: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    model: str
    usage: Optional[Dict[str, int]] = None


class EmbedRequest(BaseModel):
    texts: List[str]
    model: Optional[str] = None


class EmbedResponse(BaseModel):
    vectors: List[List[float]]
    model: str
    dimensions: int


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/complete", response_model=CompleteResponse)
async def handle_complete(req: CompleteRequest):
    """Completion endpoint — supports simple prompt or multi-turn + tools."""
    from shared.ai import complete
    from shared.ai.config import get_config

    cfg = get_config()
    model = req.model or cfg.full_model(req.purpose)

    try:
        result = complete(
            prompt=req.prompt,
            messages=req.messages,
            model=model,
            purpose=req.purpose,
            system=req.system,
            tools=req.tools,
            response_format=req.response_format,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        return CompleteResponse(
            text=result.text,
            tool_calls=result.tool_calls,
            model=model,
            usage=result.usage,
        )
    except Exception as exc:
        logger.exception("AI completion failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/embed", response_model=EmbedResponse)
async def handle_embed(req: EmbedRequest):
    """Embedding endpoint — routes cloud vs local based on model prefix."""
    from shared.ai import embed
    from shared.ai.config import get_config

    cfg = get_config()
    model = req.model or cfg.full_cloud_embedding_model()

    try:
        vectors = embed(texts=req.texts, model=model)
        dims = len(vectors[0]) if vectors else 0
        return EmbedResponse(vectors=vectors, model=model, dimensions=dims)
    except Exception as exc:
        logger.exception("AI embedding failed")
        raise HTTPException(status_code=500, detail=str(exc))
