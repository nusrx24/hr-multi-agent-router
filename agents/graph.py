"""
LangGraph pipeline for the HR Multi-Agent Router.

Wires the Orchestrator and Sub-Agent nodes together with conditional
routing edges. The graph flow is:

    1. orchestrator → classifies intent, assigns confidence
    2. router (conditional edge) → routes to the correct sub-agent
    3. sub-agent → generates domain-specific response
    4. audit_logger → records the full transaction

Exports `run_pipeline()` as the public entry point.
"""

import logging
from datetime import datetime
from typing import Any

from langgraph.graph import StateGraph, END

from agents.state import AgentState
from agents.orchestrator import orchestrator_node
from agents.sub_agents import (
    scheduling_agent_node,
    leave_agent_node,
    compliance_agent_node,
    clarification_agent_node,
)
from database import insert_audit_log
from models import AuditLogEntry

logger = logging.getLogger(__name__)


async def audit_logger_node(state: AgentState) -> dict[str, Any]:
    """
    Final node in the pipeline. Records the complete transaction
    in the append-only audit log.

    Args:
        state: Final agent state with all fields populated.

    Returns:
        Empty dict (no state changes needed).
    """
    try:
        entry = AuditLogEntry(
            timestamp=datetime.utcnow(),
            user_id=state["user_id"],
            request_text=state["request_text"],
            intent=state.get("intent", "unknown"),
            confidence=state.get("confidence", 0.0),
            sub_agent=state.get("sub_agent", "unknown"),
            response=state.get("response", ""),
            error=state.get("error"),
        )
        await insert_audit_log(entry)
        logger.info("Audit log entry created for user=%s", state["user_id"])
    except Exception as e:
        # Audit logging failures should not break the pipeline
        logger.error("Failed to write audit log: %s", str(e))

    return {}


def route_to_sub_agent(state: AgentState) -> str:
    """
    Conditional routing function for LangGraph.

    Examines the classified intent and routes to the appropriate
    sub-agent node.

    Args:
        state: Current agent state with intent set by orchestrator.

    Returns:
        The name of the next node to execute.
    """
    intent = state.get("intent", "clarification")

    route_map = {
        "scheduling": "scheduling_agent",
        "leave": "leave_agent",
        "compliance": "compliance_agent",
        "clarification": "clarification_agent",
    }

    destination = route_map.get(intent, "clarification_agent")
    logger.info("Routing to: %s (intent=%s)", destination, intent)
    return destination


def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph state machine.

    Graph Structure:
        START → orchestrator → [conditional] → sub_agent → audit_logger → END

    Returns:
        A compiled LangGraph StateGraph ready for execution.
    """
    # Define the graph with AgentState as the shared state
    graph = StateGraph(AgentState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("scheduling_agent", scheduling_agent_node)
    graph.add_node("leave_agent", leave_agent_node)
    graph.add_node("compliance_agent", compliance_agent_node)
    graph.add_node("clarification_agent", clarification_agent_node)
    graph.add_node("audit_logger", audit_logger_node)

    graph.set_entry_point("orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        route_to_sub_agent,
        {
            "scheduling_agent": "scheduling_agent",
            "leave_agent": "leave_agent",
            "compliance_agent": "compliance_agent",
            "clarification_agent": "clarification_agent",
        },
    )

    graph.add_edge("scheduling_agent", "audit_logger")
    graph.add_edge("leave_agent", "audit_logger")
    graph.add_edge("compliance_agent", "audit_logger")
    graph.add_edge("clarification_agent", "audit_logger")
    graph.add_edge("audit_logger", END)

    logger.info("LangGraph pipeline built successfully")
    return graph


_compiled_graph = None


def get_compiled_graph():
    """Get or create the compiled graph singleton."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


async def run_pipeline(user_id: str, request_text: str) -> dict:
    """
    Execute the full HR multi-agent pipeline.

    This is the main entry point called by the API layer. It:
        1. Initializes the agent state
        2. Runs the LangGraph pipeline
        3. Returns the final result

    Args:
        user_id: The requesting user's ID.
        request_text: The natural language HR request.

    Returns:
        Dict with intent, confidence, sub_agent, response, and error fields.
    """
    logger.info("Pipeline started: user=%s, request='%s'", user_id, request_text[:80])

    # Initialize state
    initial_state: AgentState = {
        "user_id": user_id,
        "request_text": request_text,
        "memory_context": "",
        "intent": None,
        "confidence": None,
        "sub_agent": None,
        "response": None,
        "error": None,
        "extracted_facts": None,
    }

    try:
        # Run the compiled graph
        compiled = get_compiled_graph()
        final_state = await compiled.ainvoke(initial_state)

        logger.info(
            "Pipeline complete: intent=%s, confidence=%s, agent=%s",
            final_state.get("intent"),
            final_state.get("confidence"),
            final_state.get("sub_agent"),
        )

        return {
            "user_id": final_state["user_id"],
            "request_text": final_state["request_text"],
            "intent": final_state.get("intent", "unknown"),
            "confidence": final_state.get("confidence", 0.0),
            "sub_agent": final_state.get("sub_agent", "unknown"),
            "response": final_state.get("response", ""),
            "error": final_state.get("error"),
        }

    except Exception as e:
        logger.error("Pipeline failed: %s", str(e))
        # Return a graceful error — never expose raw stack traces
        return {
            "user_id": user_id,
            "request_text": request_text,
            "intent": "clarification",
            "confidence": 0.0,
            "sub_agent": "ClarificationAgent",
            "response": (
                "I apologize, but I'm having trouble processing your request "
                "right now. Please try again in a moment, or contact HR "
                "directly at hr@company.com for immediate assistance."
            ),
            "error": str(e),
        }
