"""
Orchestrator Agent for the HR Multi-Agent Router.

The Orchestrator is the brain of the pipeline. It:
    1. Retrieves the user's memory context (STM + LTM).
    2. Constructs a structured prompt with context injection.
    3. Calls the Groq LLM to classify intent and assign a confidence score.
    4. Parses the structured JSON response.
    5. Extracts facts from the request for memory storage.

Includes retry logic and timeout handling for resilience.
"""

import json
import asyncio
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from agents.state import AgentState
from config import get_settings
from memory import retrieve_context, store_memory

logger = logging.getLogger(__name__)
settings = get_settings()

# ── LLM Initialization ────────────────────────────────────────

llm = ChatGroq(
    api_key=settings.groq_api_key,
    model_name=settings.model_name,
    temperature=0.1,  # Low temperature for consistent classification
    max_tokens=1024,
)

# ── System Prompt ──────────────────────────────────────────────

ORCHESTRATOR_SYSTEM_PROMPT = """You are an HR Orchestrator Agent. Your job is to:
1. Classify the user's HR request into one of these intents:
   - "scheduling": Meetings, interviews, calendar events, room bookings, flexible working hours (e.g., leaving early, making up hours, shift changes, arriving late).
   - "leave": Official paid or unpaid time off, such as PTO requests, sick leave, vacation, half-day absences, and time-off balance inquiries. Do NOT use this for daily schedule adjustments like leaving early or shifting hours.
   - "compliance": Policy questions, regulations, handbook queries, legal/HR rules, workplace concerns, harassment, discrimination, or any sensitive workplace issues.
   - "clarification": Use ONLY when the request is too vague or ambiguous to classify, OR when the request mixes multiple intents that cannot be resolved into one.

2. Assign a confidence score (0.0 to 1.0) for your classification.

3. Extract any factual information about the user that would be useful for future interactions
   (e.g., their role, department, location, preferences).

RULES:
- Respond ONLY with valid JSON. No extra text.
- If the request is clearly about one topic, assign high confidence (>= 0.7).
- If the request is ambiguous or mixes topics, assign lower confidence.
- If confidence is below 0.4, set intent to "clarification".
- Always try your best to classify before falling back to clarification.

EXAMPLES (for edge-case guidance):
- "Can I leave 2 hours early today and make it up on Saturday?" -> intent: "scheduling" (flex-time adjustment, NOT official leave)
- "I am running 30 minutes late for my shift due to traffic." -> intent: "scheduling"
- "I have a dentist appointment tomorrow morning and will be offline until noon." -> intent: "leave" (partial-day absence)
- "I need to take a half-day this Friday for personal reasons." -> intent: "leave"
- "I need to take tomorrow off sick." -> intent: "leave"
- "What are the mandatory break-time regulations for a 12-hour shift?" -> intent: "compliance" (policy question, not scheduling)
- "My manager is making me uncomfortable, what should I do?" -> intent: "compliance" (sensitive workplace issue)
- "Can you fix my Friday?" -> intent: "clarification" (too vague)
- "I want to take next Monday off, but I also need you to reschedule my afternoon meetings." -> intent: "clarification" (mixed intents)
- "I need to talk to someone about what happened yesterday." -> intent: "clarification" (unclear what happened)

Response format:
{
    "intent": "scheduling|leave|compliance|clarification",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of why this intent was chosen",
    "extracted_facts": ["fact1", "fact2"]  // Empty list if no facts found
}"""


# ── Orchestrator Node ──────────────────────────────────────────


async def orchestrator_node(state: AgentState) -> dict[str, Any]:
    """
    Main orchestrator node in the LangGraph pipeline.

    Retrieves user context, classifies intent via LLM, and returns
    the updated state with intent, confidence, and extracted facts.

    Args:
        state: Current agent state with user_id and request_text.

    Returns:
        Partial state update with memory_context, intent, confidence,
        sub_agent assignment, and extracted_facts.
    """
    user_id = state["user_id"]
    request_text = state["request_text"]

    logger.info("Orchestrator processing request from user=%s", user_id)

    try:
        # ── Step 1: Retrieve Memory Context ──
        memory_context = await retrieve_context(user_id)

        # ── Step 2: Build the Prompt ──
        user_prompt = _build_user_prompt(request_text, memory_context)

        # ── Step 3: Call LLM with Retry Logic ──
        result = await _call_llm_with_retry(user_prompt)

        # ── Step 4: Parse the Response ──
        parsed = _parse_llm_response(result)

        # ── Step 5: Apply Confidence Threshold ──
        intent = parsed["intent"]
        confidence = parsed["confidence"]

        if confidence < settings.confidence_threshold:
            intent = "clarification"
            logger.info(
                "Low confidence (%.2f < %.2f), routing to clarification",
                confidence,
                settings.confidence_threshold,
            )

        # ── Step 6: Determine Sub-Agent ──
        sub_agent = _get_sub_agent_name(intent)

        # ── Step 7: Store Request in Memory ──
        await store_memory(user_id, request_text)

        # ── Step 8: Store Extracted Facts ──
        extracted_facts = parsed.get("extracted_facts", [])
        for fact in extracted_facts:
            if fact and fact.strip():
                await store_memory(user_id, fact.strip())

        logger.info(
            "Orchestrator result: intent=%s, confidence=%.2f, sub_agent=%s",
            intent,
            confidence,
            sub_agent,
        )

        return {
            "memory_context": memory_context,
            "intent": intent,
            "confidence": confidence,
            "sub_agent": sub_agent,
            "extracted_facts": extracted_facts,
            "error": None,
        }

    except Exception as e:
        logger.error("Orchestrator error: %s", str(e))
        return {
            "memory_context": "",
            "intent": "clarification",
            "confidence": 0.0,
            "sub_agent": "ClarificationAgent",
            "extracted_facts": [],
            "error": str(e),
        }


# ── Helper Functions ───────────────────────────────────────────


def _build_user_prompt(request_text: str, memory_context: str) -> str:
    """Build the user-facing prompt with optional memory context injection."""
    parts = []

    if memory_context:
        parts.append(
            f"## User Context (from previous interactions)\n{memory_context}\n"
        )

    parts.append(f"## Current Request\n{request_text}")

    return "\n".join(parts)


async def _call_llm_with_retry(user_prompt: str) -> str:
    """
    Call the Groq LLM with retry logic and timeout handling.

    Retries up to settings.llm_max_retries times on failure.
    Each call has a timeout of settings.llm_timeout seconds.

    Args:
        user_prompt: The formatted prompt to send to the LLM.

    Returns:
        The raw text response from the LLM.

    Raises:
        RuntimeError: If all retries are exhausted.
    """
    last_error = None

    for attempt in range(1, settings.llm_max_retries + 1):
        try:
            logger.info("LLM call attempt %d/%d", attempt, settings.llm_max_retries)

            messages = [
                SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]

            # Apply timeout
            response = await asyncio.wait_for(
                llm.ainvoke(messages),
                timeout=settings.llm_timeout,
            )

            return response.content

        except asyncio.TimeoutError:
            last_error = f"LLM call timed out after {settings.llm_timeout}s (attempt {attempt})"
            logger.warning(last_error)

        except Exception as e:
            last_error = f"LLM call failed: {str(e)} (attempt {attempt})"
            logger.warning(last_error)

        # Brief delay before retry
        if attempt < settings.llm_max_retries:
            await asyncio.sleep(1)

    raise RuntimeError(f"LLM failed after {settings.llm_max_retries} attempts: {last_error}")


def _parse_llm_response(raw_response: str) -> dict:
    """
    Parse the LLM's JSON response, handling common formatting issues.

    Args:
        raw_response: Raw text from the LLM (expected to be JSON).

    Returns:
        Parsed dict with intent, confidence, reasoning, and extracted_facts.
    """
    # Clean up common issues — LLM sometimes wraps JSON in markdown code blocks
    cleaned = raw_response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON: %s", cleaned[:200])
        # Fallback — try to extract intent from the raw text
        return {
            "intent": "clarification",
            "confidence": 0.3,
            "reasoning": "Failed to parse LLM response",
            "extracted_facts": [],
        }

    # Validate required fields
    valid_intents = {"scheduling", "leave", "compliance", "clarification"}
    intent = parsed.get("intent", "clarification").lower().strip()
    if intent not in valid_intents:
        intent = "clarification"

    confidence = parsed.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, float(confidence)))

    return {
        "intent": intent,
        "confidence": confidence,
        "reasoning": parsed.get("reasoning", ""),
        "extracted_facts": parsed.get("extracted_facts", []),
    }


def _get_sub_agent_name(intent: str) -> str:
    """Map an intent to its corresponding sub-agent name."""
    agent_map = {
        "scheduling": "SchedulingAgent",
        "leave": "LeaveAgent",
        "compliance": "ComplianceAgent",
        "clarification": "ClarificationAgent",
    }
    return agent_map.get(intent, "ClarificationAgent")
