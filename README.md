# HR Multi-Agent Task Routing & Memory Engine

A multi-agent HR automation platform that routes natural language requests to specialized sub-agents using **FastAPI**, **LangGraph**, and **Groq** (open-source LLMs). Features a two-tier memory system (STM/LTM), intent classification with confidence scoring, and an append-only audit trail.

---

## Architecture Overview

```
                        ┌─────────────────┐
                        │   FastAPI API    │
                        │  POST /request   │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   Orchestrator   │
                        │  (Groq LLM)      │
                        │  Intent + Score  │
                        └────────┬────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               │                 │                  │
    ┌──────────▼──┐   ┌─────────▼──┐   ┌──────────▼───┐
    │ Scheduling  │   │   Leave     │   │ Compliance   │
    │   Agent     │   │   Agent     │   │   Agent      │
    └─────────────┘   └────────────┘   └──────────────┘
               │                 │                  │
               └─────────────────┼──────────────────┘
                                 │
                        ┌────────▼────────┐
                        │  Audit Logger   │
                        │ (Append-Only)   │
                        └─────────────────┘
```

If confidence is below **0.4**, the request routes to the **ClarificationAgent** (fallback).

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend Framework | FastAPI + Uvicorn |
| Orchestration | LangGraph (StateGraph with conditional edges) |
| LLM | Groq API — Llama-3.3-70b-versatile |
| Database | SQLite (via aiosqlite) |
| Validation | Pydantic v2 |
| Configuration | pydantic-settings + python-dotenv |
| Testing | pytest + pytest-asyncio + httpx |

---

## Setup Instructions

### Prerequisites
- Python 3.11+
- A free Groq API key ([console.groq.com](https://console.groq.com))

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/hr-multi-agent-router.git
cd hr-multi-agent-router
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
```
Edit `.env` and add your Groq API key:
```
GROQ_API_KEY=gsk_your_actual_key_here
```

### 5. Seed the Database (Optional)
```bash
python mock_data.py
```

### 6. Start the Server
```bash
python main.py
# or
uvicorn main:app --reload
```

The server starts at **http://localhost:8000**. Interactive docs at **http://localhost:8000/docs**.

---

## API Endpoints

### 1. `POST /api/v1/request` — Process an HR Request
```bash
curl -X POST http://localhost:8000/api/v1/request \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_001", "request_text": "Schedule a team meeting for tomorrow at 2pm"}'
```
**Response:**
```json
{
  "user_id": "user_001",
  "intent": "scheduling",
  "confidence": 0.9,
  "sub_agent": "SchedulingAgent",
  "response": "✅ Meeting Scheduled...",
  "timestamp": "2026-05-20T..."
}
```

### 2. `GET /api/v1/audit` — Retrieve Audit Logs
```bash
curl "http://localhost:8000/api/v1/audit?page=1&limit=10&user_id=user_001"
```

### 3. `GET /api/v1/memory/{user_id}` — Get User Memory
```bash
curl http://localhost:8000/api/v1/memory/user_001
```

### 4. `DELETE /api/v1/memory/{user_id}` — Clear User STM
```bash
curl -X DELETE http://localhost:8000/api/v1/memory/user_001
```

### 5. `GET /api/v1/health` — Health Check
```bash
curl http://localhost:8000/api/v1/health
```

---

## Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run with output
pytest tests/ -v -s
```

---

## Project Structure
```
hr-multi-agent-router/
├── main.py                  # FastAPI app entry point
├── config.py                # Settings loader (pydantic-settings)
├── database.py              # SQLite schema & CRUD operations
├── models.py                # Pydantic request/response schemas
├── memory.py                # STM/LTM engine + significance scoring
├── mock_data.py             # Database seeder with sample data
├── requirements.txt         # Pinned dependencies
├── .env.example             # Environment variable template
├── agents/
│   ├── state.py             # AgentState TypedDict
│   ├── orchestrator.py      # LLM-powered intent classification
│   ├── sub_agents.py        # Scheduling, Leave, Compliance, Clarification
│   └── graph.py             # LangGraph pipeline wiring
├── routers/
│   └── api.py               # REST API route handlers
└── tests/
    └── test_endpoints.py    # Integration tests (13 test cases)
```

---

## Memory System

| Tier | Purpose | Persistence | Threshold |
|------|---------|-------------|-----------|
| **STM** (Short-Term) | Recent conversation turns | Auto-capped at 10 per user | Score < 0.6 |
| **LTM** (Long-Term) | Important facts (role, dept, location) | Permanent | Score ≥ 0.6 |

Significance scoring uses keyword matching (50+ HR terms), regex pattern detection, and length heuristics.

---

## License

This project was built as part of an AI internship assessment.
