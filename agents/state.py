"""
Agent State definition for the HR Multi-Agent Router.

Defines the TypedDict that flows through the LangGraph pipeline,
carrying all data from request intake through routing and response.
"""

from typing import Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """
    Shared state object that flows through the LangGraph pipeline.

    Each node in the graph reads from and writes to this state.
    The state is immutable between nodes — each node returns
    a partial dict that gets merged into the state.

    Fields:
        user_id: Unique identifier for the requesting user.
        request_text: The original natural language HR request.
        memory_context: Formatted STM/LTM context string injected into prompts.
        intent: Classified intent category (scheduling, leave, compliance, clarification).
        confidence: Confidence score (0.0–1.0) for the intent classification.
        sub_agent: Name of the sub-agent that handled the request.
        response: Final response text returned to the user.
        error: Error message if something went wrong (None on success).
        extracted_facts: Facts extracted from the request for memory storage.
    """

    user_id: str
    request_text: str
    memory_context: str
    intent: Optional[str]
    confidence: Optional[float]
    sub_agent: Optional[str]
    response: Optional[str]
    error: Optional[str]
    extracted_facts: Optional[list[str]]
