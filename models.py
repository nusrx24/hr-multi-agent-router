"""
Pydantic models for the HR Multi-Agent Router.

Defines request/response schemas for the API layer, plus internal
data models for audit log entries and memory records.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────


class IntentType(str, Enum):
    """Supported HR intent categories."""

    SCHEDULING = "scheduling"
    LEAVE = "leave"
    COMPLIANCE = "compliance"
    CLARIFICATION = "clarification"


class MemoryType(str, Enum):
    """Two-tier memory classification."""

    STM = "stm"  # Short-Term Memory — recent conversation turns
    LTM = "ltm"  # Long-Term Memory — significant extracted facts


# ── API Request / Response Models ──────────────────────────────


class HRRequest(BaseModel):
    """Incoming HR request from a user."""

    user_id: str = Field(
        ...,
        description="Unique identifier for the user making the request.",
        examples=["user_001"],
    )
    request_text: str = Field(
        ...,
        description="Natural language HR request to process.",
        examples=["I need to schedule a meeting with the compliance team tomorrow at 2pm."],
    )


class HRResponse(BaseModel):
    """Response returned after processing an HR request."""

    user_id: str
    request_text: str
    intent: IntentType
    confidence: float = Field(..., ge=0.0, le=1.0)
    sub_agent: str
    response: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Audit Log Models ──────────────────────────────────────────


class AuditLogEntry(BaseModel):
    """A single audit log record. Append-only — never updated or deleted."""

    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: str
    request_text: str
    intent: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    sub_agent: str
    response: str
    error: Optional[str] = None


class AuditLogResponse(BaseModel):
    """Paginated audit log response."""

    total: int
    page: int
    limit: int
    entries: list[AuditLogEntry]


# ── Memory Models ─────────────────────────────────────────────


class MemoryEntry(BaseModel):
    """A single memory record (STM or LTM)."""

    id: Optional[int] = None
    user_id: str
    content: str
    memory_type: MemoryType
    significance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score indicating how significant this information is. >= 0.6 → LTM.",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserMemoryResponse(BaseModel):
    """All memory for a specific user, split into STM and LTM."""

    user_id: str
    stm: list[MemoryEntry] = []
    ltm: list[MemoryEntry] = []


# ── Health Check ──────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Health check response with DB connectivity status."""

    status: str = "healthy"
    database: str = "connected"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
