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
git clone https://github.com/nusrx24/hr-multi-agent-router.git
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
# Windows
copy .env.example .env

# macOS/Linux
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
This populates the database with 9 sample memory entries and runs 7 example requests through the pipeline.

### 6. Start the Server
```bash
python main.py
# or
uvicorn main:app --reload
```

The server starts at **http://localhost:8000**.  
Interactive API docs (Swagger UI) at **http://localhost:8000/docs**.

---

## User Guide — How to Use the System

### Step 1: Start the Server

```bash
python main.py
```
You should see:
```
INFO | Starting HR Multi-Agent Router...
INFO | Database initialized successfully at hr_engine.db
INFO | Uvicorn running on http://127.0.0.1:8000
```

### Step 2: Open the Interactive API Docs

Open your browser and go to: **http://localhost:8000/docs**

This gives you a Swagger UI where you can test all endpoints directly from the browser — no curl or Postman needed.

### Step 3: Submit an HR Request

Use **POST /api/v1/request** to send a natural language HR request.

**Example requests you can try:**

| Request Text | Expected Intent | Sub-Agent |
|---|---|---|
| `"Schedule a team meeting for tomorrow at 2pm"` | scheduling | SchedulingAgent |
| `"I need to take PTO next Friday"` | leave | LeaveAgent |
| `"How many sick days do I have remaining?"` | leave | LeaveAgent |
| `"What is the remote work policy?"` | compliance | ComplianceAgent |
| `"Can I leave 2 hours early and make it up Saturday?"` | scheduling | SchedulingAgent |
| `"My manager is making me uncomfortable"` | compliance | ComplianceAgent |
| `"hello"` | clarification | ClarificationAgent |

**Using Swagger UI:**
1. Click on **POST /api/v1/request** → Click **"Try it out"**
2. Paste this JSON body:
   ```json
   {
     "user_id": "user_001",
     "request_text": "I need to schedule a meeting with HR tomorrow at 10am"
   }
   ```
3. Click **"Execute"**
4. See the response with `intent`, `confidence`, `sub_agent`, and `response`

**Using curl:**
```bash
curl -X POST http://localhost:8000/api/v1/request \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_001", "request_text": "Schedule a team meeting for tomorrow at 2pm"}'
```

**Using Python:**
```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/request",
    json={
        "user_id": "user_001",
        "request_text": "I need to take PTO next Friday"
    }
)
print(response.json())
```

### Step 4: View Audit Logs

Every request is automatically logged. View them with **GET /api/v1/audit**:

```bash
# Get all audit logs (paginated)
curl "http://localhost:8000/api/v1/audit?page=1&limit=10"

# Filter by user
curl "http://localhost:8000/api/v1/audit?user_id=user_001"
```

### Step 5: Check User Memory

The system remembers important facts about users. View memory with **GET /api/v1/memory/{user_id}**:

```bash
curl http://localhost:8000/api/v1/memory/user_001
```

Response shows STM (recent turns) and LTM (important facts) separately:
```json
{
  "user_id": "user_001",
  "stm": [
    {"content": "Schedule a meeting for tomorrow", "significance_score": 0.25}
  ],
  "ltm": [
    {"content": "I am a manager in engineering", "significance_score": 0.88}
  ]
}
```

### Step 6: Clear Short-Term Memory

Clear a user's STM (LTM is preserved) with **DELETE /api/v1/memory/{user_id}**:

```bash
curl -X DELETE http://localhost:8000/api/v1/memory/user_001
```

### Step 7: Health Check

Verify the system is running with **GET /api/v1/health**:

```bash
curl http://localhost:8000/api/v1/health
```

---

## API Reference

| Endpoint | Method | Description | Parameters |
|----------|--------|-------------|------------|
| `/api/v1/request` | POST | Process an HR request | Body: `{"user_id": "...", "request_text": "..."}` |
| `/api/v1/audit` | GET | Retrieve audit logs | Query: `page`, `limit`, `user_id` (all optional) |
| `/api/v1/memory/{user_id}` | GET | Get user's STM + LTM | Path: `user_id` |
| `/api/v1/memory/{user_id}` | DELETE | Clear user's STM only | Path: `user_id` |
| `/api/v1/health` | GET | Health check | None |

---

## Running Tests

```bash
# Run all integration tests
pytest tests/ -v

# Run with full output
pytest tests/ -v -s
```

Expected result: **11 passed** ✅

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
├── TECHNICAL_REPORT.md      # Architecture decisions & trade-offs
├── agents/
│   ├── state.py             # AgentState TypedDict
│   ├── orchestrator.py      # LLM-powered intent classification
│   ├── sub_agents.py        # Scheduling, Leave, Compliance, Clarification
│   └── graph.py             # LangGraph pipeline wiring
├── routers/
│   └── api.py               # REST API route handlers
└── tests/
    └── test_endpoints.py    # Integration tests (11 test cases)
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

This project was built as part of an AI internship assessment for ZeloraTech Pvt Ltd.
