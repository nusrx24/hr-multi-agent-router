# HR Multi-Agent Task Routing and Memory Engine

This document outlines the requirements, architectural design, and step-by-step implementation plan for building the HR Multi-Agent Automation Platform. 

## Background Context
You successfully built the Support Ticket Classifier. This new project takes those concepts to the next level. 
* **Ticket Classifier:** Focused on categorizing text and extracting metadata using a single LLM pass or simple pipeline.
* **HR Multi-Agent Router:** Involves **Stateful Orchestration**. You will use LangGraph not just to classify, but to route requests to specialized "Sub-Agents" (Scheduling, Leave, Compliance), inject historical context (STM/LTM), and maintain a strict append-only audit trail for every action.

## Project Decisions
* **Workspace:** We will build this project from scratch in a new folder: `d:\LLM model\hr-multi-agent-router`.
* **LLM Provider:** We will use **Groq** via `langchain-groq` to serve Open-Source models (like Llama-3-70b).
* **Repository:** A new Git repository will be initialized in this folder for your final submission.

---

## 🏗️ System Architecture

### 1. Database Layer (SQLite)
* **Memory Table (STM/LTM):** Stores user context. 
  * *STM (Short-Term Memory):* Recent conversation turns (e.g., "I need time off").
  * *LTM (Long-Term Memory):* Important extracted facts with a **significance score** (e.g., "User is a manager", "User works in NY").
* **Audit Log Table:** A strict append-only table recording every request, intent classification, confidence score, and routing decision.

### 2. Orchestration Layer (LangGraph)
* **Orchestrator Node:** Receives the natural language request, queries the DB for STM/LTM context, and injects it into the prompt. It outputs an Intent, a Confidence Score, and the selected Sub-Agent.
* **Router Edge:** A conditional edge in LangGraph that directs the flow based on the Orchestrator's intent.
* **Sub-Agent Nodes (Stubs):** 
  * `SchedulingAgent`: Handles meeting/interview requests.
  * `LeaveAgent`: Handles PTO/sick leave.
  * `ComplianceAgent`: Handles policy questions.
  * `ClarificationAgent`: (Fallback) Triggered when confidence is low.

### 3. API Layer (FastAPI)
Exposes 4 core REST endpoints:
* `POST /api/v1/request`: Main entry point for user prompts.
* `GET /api/v1/audit`: Retrieves paginated audit logs.
* `GET /api/v1/memory`: Fetches a user's STM and LTM data.
* `GET /api/v1/health`: Basic health monitoring endpoint.

---

## 🛠️ Step-by-Step Implementation Plan

### Phase 1: Project Initialization & Configuration
* Create the new project directory and setup a virtual environment.
* Install dependencies: `fastapi`, `uvicorn`, `langgraph`, `langchain`, `sqlite3` (or `sqlmodel`/`sqlalchemy`), `pydantic`, `python-dotenv`.
* Setup `.env` for API keys and configuration.

### Phase 2: Database & Memory Engine
* Implement the SQLite schema for the `AuditLog` (append-only logic).
* Implement the SQLite schema for `Memory` (STM vs LTM).
* Build CRUD utility functions, specifically the **Significance Scoring Logic** (e.g., deciding if a piece of information is trivial or needs to be saved to LTM).

### Phase 3: LangGraph Multi-Agent Orchestration
* Define the `AgentState` (TypedDict) holding the input, context, intent, confidence, and output.
* **Build the Orchestrator:** Prompt engineering for intent classification and confidence scoring.
* **Build Sub-Agent Stubs:** Create the Mock/Stub logic for Scheduling, Leave, Compliance, and Clarification.
* **Define the Graph:** Wire the nodes together with conditional routing, including timeout and retry logic.
* **Fallback Mechanisms:** Ensure low-confidence scores safely route to Clarification without exposing Python stack traces.

### Phase 4: FastAPI Integration
* Construct the REST API routers.
* Wire the `/request` endpoint to trigger the LangGraph execution.
* Wire the `/audit` and `/memory` endpoints to the SQLite database layer.
* Add structured error handling (polite fallback responses instead of 500 Server Errors).

### Phase 5: Testing & Technical Report
* Create `mock_data.py` to seed the database for testing.
* Write unit tests/scripts to verify all 5 endpoints.
* Generate the final **Technical Report** explaining trade-offs, architecture decisions, and system boundaries.
* Prepare a ZIP archive / Github structure with local setup instructions.
