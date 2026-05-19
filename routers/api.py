"""
API route handlers for the HR Multi-Agent Router.

Exposes 5 REST endpoints:
    - POST /api/v1/request   — Process an HR request through the pipeline
    - GET  /api/v1/audit     — Paginated audit log retrieval
    - GET  /api/v1/memory/{user_id}    — Fetch user's STM + LTM
    - DELETE /api/v1/memory/{user_id}  — Clear user's STM
    - GET  /api/v1/health    — Health check with DB status
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from agents.graph import run_pipeline
from database import get_audit_logs, get_user_memory, clear_user_stm, check_db_health
from models import (
    HRRequest,
    HRResponse,
    AuditLogResponse,
    UserMemoryResponse,
    HealthResponse,
    MemoryType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["HR Multi-Agent Router"])


# ── POST /request ──────────────────────────────────────────────


@router.post(
    "/request",
    response_model=HRResponse,
    summary="Process an HR request",
    description="Submit a natural language HR request. The orchestrator classifies "
    "the intent, routes to the appropriate sub-agent, and returns the response.",
)
async def process_request(request: HRRequest) -> HRResponse:
    """
    Main entry point for HR requests.

    The request flows through the LangGraph pipeline:
        Orchestrator → Router → Sub-Agent → Audit Logger
    """
    logger.info(
        "API /request: user=%s, text='%s'",
        request.user_id,
        request.request_text[:80],
    )

    result = await run_pipeline(request.user_id, request.request_text)

    return HRResponse(
        user_id=result["user_id"],
        request_text=result["request_text"],
        intent=result["intent"],
        confidence=result["confidence"],
        sub_agent=result["sub_agent"],
        response=result["response"],
        timestamp=datetime.utcnow(),
    )


# ── GET /audit ─────────────────────────────────────────────────


@router.get(
    "/audit",
    response_model=AuditLogResponse,
    summary="Retrieve audit logs",
    description="Fetch paginated audit log entries. Optionally filter by user_id.",
)
async def get_audit(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Entries per page"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
) -> AuditLogResponse:
    """Retrieve paginated, append-only audit log entries."""
    logger.info("API /audit: page=%d, limit=%d, user_id=%s", page, limit, user_id)

    entries, total = await get_audit_logs(page=page, limit=limit, user_id=user_id)

    return AuditLogResponse(
        total=total,
        page=page,
        limit=limit,
        entries=entries,
    )


# ── GET /memory/{user_id} ─────────────────────────────────────


@router.get(
    "/memory/{user_id}",
    response_model=UserMemoryResponse,
    summary="Get user memory",
    description="Retrieve all STM (Short-Term) and LTM (Long-Term) memory for a user.",
)
async def get_memory(user_id: str) -> UserMemoryResponse:
    """Fetch a user's full memory context, split into STM and LTM."""
    logger.info("API /memory: user=%s", user_id)

    all_memories = await get_user_memory(user_id)

    stm = [m for m in all_memories if m.memory_type == MemoryType.STM]
    ltm = [m for m in all_memories if m.memory_type == MemoryType.LTM]

    return UserMemoryResponse(user_id=user_id, stm=stm, ltm=ltm)


# ── DELETE /memory/{user_id} ───────────────────────────────────


@router.delete(
    "/memory/{user_id}",
    summary="Clear user STM",
    description="Clear all Short-Term Memory for a user. LTM is preserved.",
)
async def delete_user_stm(user_id: str) -> dict:
    """Clear a user's STM entries. LTM (important facts) is never deleted."""
    logger.info("API DELETE /memory: user=%s", user_id)

    deleted_count = await clear_user_stm(user_id)

    return {
        "message": f"Cleared {deleted_count} STM entries for user {user_id}",
        "user_id": user_id,
        "deleted_count": deleted_count,
    }


# ── GET /health ────────────────────────────────────────────────


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the API and database connectivity.",
)
async def health_check() -> HealthResponse:
    """Basic health monitoring endpoint with DB connectivity status."""
    db_healthy = await check_db_health()

    return HealthResponse(
        status="healthy" if db_healthy else "degraded",
        database="connected" if db_healthy else "disconnected",
        timestamp=datetime.utcnow(),
    )
