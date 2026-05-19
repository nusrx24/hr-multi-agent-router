"""
Endpoint integration tests for the HR Multi-Agent Router.

Tests all 5 API endpoints using httpx.AsyncClient against
the FastAPI test client (no live server needed).
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import app
from database import init_db


@pytest_asyncio.fixture
async def client():
    """Create an async test client with DB initialized."""
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Health Endpoint ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /api/v1/health should return 200 with healthy status."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "timestamp" in data


# ── Root Endpoint ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """GET / should return service info with all endpoint paths."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "HR Multi-Agent Router"
    assert "endpoints" in data
    assert len(data["endpoints"]) == 5


# ── Request Endpoint ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_request_endpoint_scheduling(client):
    """POST /api/v1/request with a scheduling query should classify correctly."""
    response = await client.post(
        "/api/v1/request",
        json={
            "user_id": "test_user",
            "request_text": "Schedule a meeting with the team for tomorrow at 2pm",
        },
        timeout=30,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "scheduling"
    assert data["confidence"] >= 0.5
    assert data["sub_agent"] == "SchedulingAgent"
    assert len(data["response"]) > 0


@pytest.mark.asyncio
async def test_request_endpoint_leave(client):
    """POST /api/v1/request with a leave query should classify correctly."""
    response = await client.post(
        "/api/v1/request",
        json={
            "user_id": "test_user",
            "request_text": "I want to request PTO for next Monday and Tuesday",
        },
        timeout=30,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "leave"
    assert data["confidence"] >= 0.5
    assert data["sub_agent"] == "LeaveAgent"


@pytest.mark.asyncio
async def test_request_endpoint_compliance(client):
    """POST /api/v1/request with a policy query should classify correctly."""
    response = await client.post(
        "/api/v1/request",
        json={
            "user_id": "test_user",
            "request_text": "What is the company policy on remote work?",
        },
        timeout=30,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "compliance"
    assert data["confidence"] >= 0.5
    assert data["sub_agent"] == "ComplianceAgent"


@pytest.mark.asyncio
async def test_request_endpoint_validation(client):
    """POST /api/v1/request with missing fields should return 422."""
    response = await client.post("/api/v1/request", json={})
    assert response.status_code == 422


# ── Audit Endpoint ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_endpoint(client):
    """GET /api/v1/audit should return paginated audit entries."""
    # First, make a request to generate an audit entry
    await client.post(
        "/api/v1/request",
        json={
            "user_id": "audit_test_user",
            "request_text": "Book a conference room for Friday",
        },
        timeout=30,
    )

    # Now retrieve audit logs
    response = await client.get("/api/v1/audit", params={"page": 1, "limit": 10})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["page"] == 1
    assert data["limit"] == 10
    assert len(data["entries"]) >= 1

    # Each entry should have required fields
    entry = data["entries"][0]
    assert "user_id" in entry
    assert "intent" in entry
    assert "confidence" in entry
    assert "sub_agent" in entry
    assert "response" in entry
    assert "timestamp" in entry


@pytest.mark.asyncio
async def test_audit_endpoint_filter_by_user(client):
    """GET /api/v1/audit with user_id filter should only return that user's entries."""
    response = await client.get(
        "/api/v1/audit",
        params={"user_id": "audit_test_user", "page": 1, "limit": 10},
    )
    assert response.status_code == 200
    data = response.json()
    for entry in data["entries"]:
        assert entry["user_id"] == "audit_test_user"


# ── Memory Endpoint ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_get_endpoint(client):
    """GET /api/v1/memory/{user_id} should return STM and LTM lists."""
    # Make a request to generate memory
    await client.post(
        "/api/v1/request",
        json={
            "user_id": "memory_test_user",
            "request_text": "I am a manager in the engineering department",
        },
        timeout=30,
    )

    response = await client.get("/api/v1/memory/memory_test_user")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "memory_test_user"
    assert "stm" in data
    assert "ltm" in data
    assert isinstance(data["stm"], list)
    assert isinstance(data["ltm"], list)


@pytest.mark.asyncio
async def test_memory_delete_endpoint(client):
    """DELETE /api/v1/memory/{user_id} should clear STM only."""
    response = await client.delete("/api/v1/memory/memory_test_user")
    assert response.status_code == 200
    data = response.json()
    assert "deleted_count" in data
    assert data["user_id"] == "memory_test_user"

    # Verify STM is cleared
    response = await client.get("/api/v1/memory/memory_test_user")
    data = response.json()
    assert len(data["stm"]) == 0


@pytest.mark.asyncio
async def test_memory_nonexistent_user(client):
    """GET /api/v1/memory for a nonexistent user should return empty lists."""
    response = await client.get("/api/v1/memory/nonexistent_user_xyz")
    assert response.status_code == 200
    data = response.json()
    assert len(data["stm"]) == 0
    assert len(data["ltm"]) == 0
