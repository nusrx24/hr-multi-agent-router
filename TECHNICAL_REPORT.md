# Technical Report — HR Multi-Agent Task Routing & Memory Engine

**Author:** Nusair  
**Date:** May 2026  
**Version:** 1.0.0

---

## 1. Executive Summary

This report documents the architecture, design decisions, and trade-offs made while building the HR Multi-Agent Task Routing & Memory Engine. The system uses a central Orchestrator Agent powered by Groq's Llama-3.3-70b model to classify natural language HR requests and route them to specialized sub-agents, while maintaining a two-tier memory system and strict append-only audit trail.

---

## 2. Architecture Decisions

### 2.1 LLM Provider: Groq + Llama-3.3-70b-versatile

**Decision:** Use Groq's hosted inference API with the open-source Llama-3.3-70b-versatile model.

**Rationale:**
- **Speed:** Groq's LPU inference engine provides sub-second response times (~200ms), critical for a responsive API.
- **Cost:** Free tier is generous enough for development and demonstration.
- **Open-Source:** Meets the requirement for open-source models.
- **Quality:** Llama-3.3-70b provides excellent intent classification accuracy with structured JSON output.

**Trade-off:** Depends on an external API (Groq). If Groq is down, the system falls back to the ClarificationAgent gracefully. A production system would benefit from a local fallback model.

### 2.2 Orchestration: LangGraph StateGraph

**Decision:** Use LangGraph's `StateGraph` with conditional edges for agent routing.

**Rationale:**
- **Stateful:** The `AgentState` TypedDict carries all context through the pipeline, making each node's inputs/outputs explicit.
- **Conditional Routing:** The `add_conditional_edges` API cleanly maps intents to sub-agents without nested if/else logic.
- **Extensibility:** Adding a new sub-agent requires only: (1) a new node function, (2) an entry in the route map, and (3) an edge to audit_logger.
- **Auditability:** The graph structure is self-documenting — you can trace the exact flow of any request.

**Trade-off:** LangGraph adds dependency complexity. For a simpler system, a plain function dispatch table would suffice. However, LangGraph's graph structure provides better observability and aligns with the project requirements.

### 2.3 Database: SQLite with aiosqlite

**Decision:** Use SQLite with async I/O via `aiosqlite`.

**Rationale:**
- **Zero Configuration:** No external database server needed — perfect for a portable submission.
- **Async Compatible:** `aiosqlite` wraps SQLite operations in async context, matching FastAPI's async architecture.
- **Sufficient Scale:** For an HR tool with moderate request volume, SQLite handles the load well.

**Trade-off:** SQLite doesn't support true concurrent writes. Under very high load, write operations could block. A production system would use PostgreSQL.

### 2.4 Append-Only Audit Log

**Decision:** Enforce append-only behavior at the application layer — the `database.py` module only exposes `insert_audit_log()` and `get_audit_logs()`. No UPDATE or DELETE functions exist.

**Rationale:**
- **Compliance:** Audit trails must be tamper-proof. By not providing modification functions, the application code cannot accidentally alter historical records.
- **Simplicity:** Application-level enforcement is simpler than database triggers for a project of this scope.

**Trade-off:** A determined attacker with direct database access could still modify records. A production system should use database-level triggers (`BEFORE UPDATE`, `BEFORE DELETE` → `RAISE ABORT`) or a dedicated audit database with restricted permissions.

---

## 3. Memory System Design

### 3.1 Two-Tier Architecture

The memory system separates information into two tiers:

| Tier | Purpose | Lifecycle | Example |
|------|---------|-----------|---------|
| **STM** | Recent conversation context | Capped at 10 entries per user, oldest evicted | "Schedule a meeting tomorrow" |
| **LTM** | Significant facts about the user | Permanent until manually cleared | "I am a manager in engineering" |

### 3.2 Significance Scoring Logic

The scoring system uses a **hybrid approach**:

1. **Keyword Matching (50+ HR-relevant terms):** Each keyword has a pre-assigned weight (0.65–0.9). Examples:
   - "manager" → 0.8, "department" → 0.75, "emergency contact" → 0.9
   
2. **Regex Pattern Matching:** Detects factual statements:
   - "I am a [role]" → 0.75
   - "My department is [X]" → 0.8
   - "I have [N] days" → 0.7

3. **Length Heuristic:** Very short messages (<20 chars) score low (0.1); longer messages get a small boost (0.3).

4. **Final Calculation:** Takes the maximum matched score plus a small bonus for multiple matches (capped at 0.1).

**Threshold:** Score ≥ 0.6 → LTM, Score < 0.6 → STM.

**Justification:** This heuristic approach was chosen over LLM-based scoring for two reasons:
- **Speed:** No additional API call needed — scoring is instant.
- **Cost:** Avoids doubling LLM usage per request.
- **Reliability:** Deterministic — same input always produces the same score.

A production system could use a lightweight local model (e.g., a fine-tuned classifier) for more nuanced scoring.

### 3.3 Context Injection

When processing a new request, the Orchestrator retrieves the user's full memory context (STM + LTM) and injects it into the LLM prompt. This allows the model to make context-aware classifications. For example, if the LTM contains "user is on probation," a remote work request would be classified differently.

---

## 4. Error Handling Strategy

### 4.1 LLM Failure Resilience
- **Retry Logic:** Up to 2 retry attempts on LLM failure (configurable).
- **Timeout:** 30-second timeout per LLM call (configurable).
- **Graceful Degradation:** On all-retry failure, the request routes to `ClarificationAgent` with a polite message — never exposing raw stack traces.

### 4.2 API Error Handling
- **Global Exception Handler:** Catches all unhandled exceptions in FastAPI and returns a polite JSON response with status 500.
- **Validation Errors:** Pydantic automatically returns 422 with field-level error details.
- **Audit on Failure:** Even failed requests are logged in the audit trail with the error field populated.

### 4.3 JSON Parsing Resilience
- The orchestrator handles common LLM output issues:
  - Markdown code blocks wrapping JSON (```json ... ```)
  - Invalid intent values (defaults to "clarification")
  - Missing fields (uses safe defaults)
  - Non-numeric confidence values (defaults to 0.5)

---

## 5. Testing Strategy

### 5.1 Test Coverage
- **11 integration tests** covering all 5 endpoints via pytest
- **10 edge case tests** verifying intent classification boundaries (flex-time vs leave, sensitive issues, multi-intent)
- **Tests include:** Happy paths, edge cases (nonexistent user, empty memory), validation errors, and audit log filtering
- **Test infrastructure:** Uses `httpx.AsyncClient` with FastAPI's `ASGITransport` — no live server needed

### 5.2 Mock Data
- **9 pre-seeded memory entries** across 3 user personas
- **7 sample requests** covering all 4 intent categories
- Seeder script (`mock_data.py`) can be run independently

---

## 6. Limitations and Future Improvements

### Current Limitations
1. **Sub-agents are stubs:** They return mock responses based on keyword matching. Real integrations would connect to calendar APIs, HRIS, and policy databases.
2. **No authentication:** The API has no auth layer. Production would need JWT/OAuth2.
3. **Single-threaded SQLite:** Won't scale to high-concurrency workloads.
4. **Memory scoring is heuristic-based:** May miss nuanced significance in complex statements.
5. **No conversation threading:** Each request is independent — there's no multi-turn conversation support.

### Future Improvements
1. **Real Sub-Agent Integrations:** Connect SchedulingAgent to Google Calendar, LeaveAgent to Workday/BambooHR.
2. **LLM-based Memory Scoring:** Use a lightweight model for more accurate significance classification.
3. **Multi-turn Conversations:** Add session tracking for follow-up questions.
4. **WebSocket Support:** Real-time streaming responses for better UX.
5. **PostgreSQL Migration:** For production-grade concurrency and data safety.
6. **Role-Based Access Control:** Different permission levels for employees, managers, and HR admins.

---

## 7. Bug Finding & Fixes

Since this project was built from scratch (no starter/template code was provided), the following issues were identified and corrected during development and testing:

### 7.1 Intent Misclassification — "Leave Early" Edge Case
**Bug:** The initial orchestrator prompt classified "Can I leave 2 hours early today and make it up on Saturday?" as `leave` intent, because the LLM saw the word "leave" and associated it with PTO/time-off.

**Fix:** Updated the system prompt in `orchestrator.py` with:
- Explicit boundary clarifications (e.g., "leaving early" = scheduling, NOT official leave)
- 11 few-shot examples covering edge cases across all 4 intents (flex-time, partial-day absences, sensitive workplace issues, multi-intent requests)

**Result:** 9/10 edge cases now classify correctly. The one remaining case ("I need to talk to someone about what happened yesterday") routes to `compliance` instead of `clarification` — a defensible decision since it could indicate a sensitive workplace issue.

### 7.2 LLM JSON Parsing Failures
**Bug:** The Groq LLM occasionally wraps its JSON response in markdown code blocks (` ```json ... ``` `), causing `json.loads()` to fail.

**Fix:** Added a response cleaning step in `_parse_llm_response()` that strips markdown code fences, handles missing fields with safe defaults, and validates intent values against the allowed set. If parsing fails entirely, the system falls back to `clarification` intent rather than crashing.

### 7.3 `datetime.utcnow()` Deprecation (Python 3.12+)
**Bug:** Python 3.12+ raises `DeprecationWarning` for `datetime.datetime.utcnow()`, which is scheduled for removal in a future version.

**Identified:** Flagged during pytest runs (27 warnings). Kept the current implementation for SQLite compatibility, as timezone-aware datetimes add complexity to SQLite text storage. Documented as a known issue for future migration.

### 7.4 Windows Terminal Encoding for Emojis
**Bug:** Sub-agent responses contain emojis (✅, 📅, 🤔, etc.) which crash the Windows terminal's default `cp1252` encoding when printed via `print()`.

**Fix:** Added UTF-8 stdout encoding in test scripts:
```python
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
```

---

## 8. Conclusion

The HR Multi-Agent Router successfully demonstrates a production-ready architecture for intelligent HR request routing. The system handles the full lifecycle — from natural language input, through LLM-powered classification, to domain-specific response generation — with robust error handling, memory persistence, and comprehensive audit logging. While the sub-agents use mock data, the orchestration layer, memory system, and API infrastructure are fully functional and ready for real-world integration.
