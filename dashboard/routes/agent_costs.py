"""Agent cost tracking — reads OpenCode's SQLite database.

OpenCode stores cost and token data per message in its local database.
This module reads that data (read-only) and aggregates it for the
dashboard's AI Monitor panel.

Database location: ``~/.local/share/opencode/opencode.db``
Tables used: ``message`` (cost/token JSON), ``session`` (project/agent context)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query

from dashboard.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

OPENCODE_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def _get_db_path() -> Optional[Path]:
    """Return the OpenCode database path if it exists."""
    if OPENCODE_DB.exists():
        return OPENCODE_DB
    return None


def _query_costs(days: int = 30, project: Optional[str] = None, include_personal: bool = False) -> dict:
    """Read and aggregate cost data from OpenCode's database."""
    db_path = _get_db_path()
    if not db_path:
        return {"error": "OpenCode database not found", "path": str(OPENCODE_DB)}

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        return {"error": f"Cannot open database: {e}"}

    try:
        cutoff_ms = int(
            (datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000
        )

        # Build query
        where = "WHERE json_extract(m.data, '$.cost') > 0 AND m.time_created >= ?"
        params: list = [cutoff_ms]

        if not include_personal:
            # Exclude personal OpenCode sessions (build, explore, general).
            # Only show war-room agent roles (engineer, architect, qa, etc.)
            _PERSONAL_AGENTS = ("build", "explore", "general")
            where += " AND json_extract(m.data, '$.agent') NOT IN (?, ?, ?)"
            params.extend(_PERSONAL_AGENTS)
        if project:
            where += " AND s.directory LIKE ?"
            params.append(f"%{project}%")

        rows = conn.execute(
            f"""
            SELECT m.data, m.time_created, s.directory
            FROM message m
            JOIN session s ON m.session_id = s.id
            {where}
            ORDER BY m.time_created DESC
            """,
            params,
        ).fetchall()

        # Aggregate
        total_cost = 0.0
        total_messages = 0
        by_project: dict = defaultdict(
            lambda: {"cost": 0.0, "calls": 0, "tokens": 0}
        )
        by_model: dict = defaultdict(lambda: {"cost": 0.0, "calls": 0})
        by_agent: dict = defaultdict(lambda: {"cost": 0.0, "calls": 0})
        by_day: dict = defaultdict(lambda: {"cost": 0.0, "calls": 0})

        min_ts = None
        max_ts = None

        for data_str, ts_ms, directory in rows:
            try:
                d = json.loads(data_str)
            except (json.JSONDecodeError, TypeError):
                continue

            cost = d.get("cost", 0)
            if not cost:
                continue

            tokens = d.get("tokens", {})
            model_id = d.get("modelID", "unknown")
            provider_id = d.get("providerID", "unknown")
            agent = d.get("agent", "unknown")
            total_tokens = tokens.get("total", 0)

            total_cost += cost
            total_messages += 1

            # Track date range
            if min_ts is None or ts_ms < min_ts:
                min_ts = ts_ms
            if max_ts is None or ts_ms > max_ts:
                max_ts = ts_ms

            # By project (use last path segment as name)
            proj_name = (
                directory.rstrip("/").rsplit("/", 1)[-1] if directory else "unknown"
            )
            by_project[proj_name]["cost"] += cost
            by_project[proj_name]["calls"] += 1
            by_project[proj_name]["tokens"] += total_tokens

            # By model
            model_key = f"{provider_id}/{model_id}"
            by_model[model_key]["cost"] += cost
            by_model[model_key]["calls"] += 1

            # By agent
            by_agent[agent]["cost"] += cost
            by_agent[agent]["calls"] += 1

            # By day
            day_str = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
            by_day[day_str]["cost"] += cost
            by_day[day_str]["calls"] += 1

        # Format results
        date_from = (
            datetime.fromtimestamp(min_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            if min_ts
            else None
        )
        date_to = (
            datetime.fromtimestamp(max_ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            if max_ts
            else None
        )

        return {
            "total_cost": round(total_cost, 4),
            "total_messages": total_messages,
            "date_range": {"from": date_from, "to": date_to},
            "by_project": sorted(
                [
                    {
                        "name": k,
                        "cost": round(v["cost"], 4),
                        "calls": v["calls"],
                        "tokens": v["tokens"],
                    }
                    for k, v in by_project.items()
                ],
                key=lambda x: -x["cost"],
            ),
            "by_model": sorted(
                [
                    {
                        "model": k.split("/", 1)[-1] if "/" in k else k,
                        "provider": k.split("/", 1)[0] if "/" in k else "unknown",
                        "cost": round(v["cost"], 4),
                        "calls": v["calls"],
                    }
                    for k, v in by_model.items()
                ],
                key=lambda x: -x["cost"],
            ),
            "by_agent": sorted(
                [
                    {
                        "agent": k,
                        "cost": round(v["cost"], 4),
                        "calls": v["calls"],
                    }
                    for k, v in by_agent.items()
                ],
                key=lambda x: -x["cost"],
            ),
            "by_day": sorted(
                [
                    {
                        "date": k,
                        "cost": round(v["cost"], 4),
                        "calls": v["calls"],
                    }
                    for k, v in by_day.items()
                ],
                key=lambda x: x["date"],
            ),
        }
    except Exception as e:
        logger.exception("Error reading OpenCode database")
        return {"error": str(e)}
    finally:
        conn.close()


@router.get("/api/ai/agent-costs")
async def get_agent_costs(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    project: Optional[str] = Query(None, description="Filter by project name"),
    include_personal: bool = Query(False, description="Include personal sessions (build, explore, general)"),
    user: dict = Depends(get_current_user),
):
    """Aggregate agent LLM costs from OpenCode's database.

    Reads the local OpenCode SQLite database (read-only) and returns
    cost breakdowns by project, model, agent role, and day.

    By default, only war-room agent sessions (engineer, architect, qa, etc.)
    are included. Set ``include_personal=true`` to include personal coding
    sessions (build, explore, general).
    """
    return _query_costs(days=days, project=project, include_personal=include_personal)
