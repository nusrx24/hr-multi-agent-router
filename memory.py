"""
Memory Engine for the HR Multi-Agent Router.

Implements the two-tier memory system:
    - STM (Short-Term Memory): Recent conversation turns, auto-expires.
    - LTM (Long-Term Memory): Important extracted facts that persist.

Includes the Significance Scoring Logic that determines whether a
piece of information is trivial (STM) or significant (LTM).
"""

import logging
import re
from datetime import datetime

from config import get_settings
from database import insert_memory, get_user_memory, enforce_stm_limit
from models import MemoryEntry, MemoryType

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Significance Scoring ──────────────────────────────────────

# Keywords and patterns that indicate high-significance information.
# These are facts about the user or organization that would be useful
# for future interactions — stored as LTM.

HIGH_SIGNIFICANCE_KEYWORDS: dict[str, float] = {
    # Role & Identity
    "manager": 0.8,
    "director": 0.85,
    "supervisor": 0.8,
    "team lead": 0.8,
    "intern": 0.7,
    "employee id": 0.9,
    "department": 0.75,
    "hr": 0.7,
    "engineering": 0.7,
    "finance": 0.7,
    "marketing": 0.7,
    "operations": 0.7,
    # Location & Schedule
    "location": 0.7,
    "office": 0.65,
    "remote": 0.7,
    "timezone": 0.75,
    "shift": 0.7,
    "work from home": 0.7,
    "new york": 0.65,
    "san francisco": 0.65,
    # Policy & Compliance
    "policy": 0.8,
    "regulation": 0.85,
    "compliance": 0.8,
    "handbook": 0.75,
    "contract": 0.8,
    "probation": 0.75,
    "termination": 0.85,
    # Leave & Benefits
    "pto balance": 0.8,
    "sick leave": 0.7,
    "maternity": 0.8,
    "paternity": 0.8,
    "vacation days": 0.75,
    "benefits": 0.7,
    # Personal context
    "preferred name": 0.8,
    "accommodation": 0.85,
    "disability": 0.85,
    "emergency contact": 0.9,
}

# Patterns that indicate factual/significant statements
FACT_PATTERNS: list[tuple[str, float]] = [
    (r"\bi am (?:a|an|the) \w+", 0.75),         # "I am a manager"
    (r"\bi work (?:in|at|for) \w+", 0.7),        # "I work in engineering"
    (r"\bmy (?:name|role|title|department) is", 0.8),  # "My department is..."
    (r"\bi(?:'m| am) based (?:in|at)", 0.7),     # "I'm based in NY"
    (r"\bi have \d+ (?:days?|hours?)", 0.7),     # "I have 5 days of PTO"
    (r"\bi(?:'ve| have) been (?:here|working)", 0.65),  # Tenure info
]


def calculate_significance_score(text: str) -> float:
    """
    Calculate a significance score for a piece of text.

    The scoring logic uses a hybrid approach:
        1. Keyword matching — checks for HR-relevant keywords.
        2. Pattern matching — detects factual statements about the user.
        3. Length heuristic — very short messages are usually less significant.

    Args:
        text: The text content to score.

    Returns:
        A float between 0.0 and 1.0 indicating significance.
        Scores >= settings.significance_threshold (0.6) → stored as LTM.
        Scores < settings.significance_threshold → stored as STM.
    """
    text_lower = text.lower().strip()

    if not text_lower:
        return 0.0

    scores: list[float] = []

    # ── 1. Keyword Matching ──
    for keyword, weight in HIGH_SIGNIFICANCE_KEYWORDS.items():
        if keyword in text_lower:
            scores.append(weight)

    # ── 2. Pattern Matching ──
    for pattern, weight in FACT_PATTERNS:
        if re.search(pattern, text_lower):
            scores.append(weight)

    # ── 3. Length Heuristic ──
    # Very short messages (< 20 chars) are likely greetings or acknowledgments
    if len(text_lower) < 20:
        scores.append(0.1)
    elif len(text_lower) > 100:
        # Longer messages more likely contain useful context
        scores.append(0.3)

    # ── Calculate Final Score ──
    if not scores:
        # Default score for unmatched content
        return 0.25

    # Use the maximum matched score, slightly boosted if multiple matches
    max_score = max(scores)
    match_bonus = min(0.1, len(scores) * 0.02)  # Small bonus for multiple matches
    final_score = min(1.0, max_score + match_bonus)

    return round(final_score, 2)


def classify_memory_type(significance_score: float) -> MemoryType:
    """
    Classify whether information should be STM or LTM based on its
    significance score.

    Args:
        significance_score: The calculated significance score (0.0 - 1.0).

    Returns:
        MemoryType.LTM if score >= threshold, otherwise MemoryType.STM.
    """
    if significance_score >= settings.significance_threshold:
        return MemoryType.LTM
    return MemoryType.STM


# ── Public API ─────────────────────────────────────────────────


async def store_memory(user_id: str, content: str) -> MemoryEntry:
    """
    Analyze content, score its significance, and store it in the
    appropriate memory tier (STM or LTM).

    Also enforces the STM entry limit per user.

    Args:
        user_id: The user this memory belongs to.
        content: The text content to store.

    Returns:
        The created MemoryEntry with its classification.
    """
    # Score and classify
    score = calculate_significance_score(content)
    mem_type = classify_memory_type(score)

    entry = MemoryEntry(
        user_id=user_id,
        content=content,
        memory_type=mem_type,
        significance_score=score,
        created_at=datetime.utcnow(),
    )

    # Persist to database
    entry_id = await insert_memory(entry)
    entry.id = entry_id

    # Enforce STM limit (keep only the most recent N entries)
    if mem_type == MemoryType.STM:
        await enforce_stm_limit(user_id, settings.max_stm_entries)

    logger.info(
        "Stored memory: user=%s, type=%s, score=%.2f, content='%s'",
        user_id,
        mem_type.value,
        score,
        content[:50],
    )

    return entry


async def retrieve_context(user_id: str) -> str:
    """
    Retrieve and format all relevant memory for a user, combining
    STM and LTM into a context string suitable for prompt injection.

    Args:
        user_id: The user whose context to retrieve.

    Returns:
        A formatted string with the user's memory context.
        Returns an empty string if no memory exists.
    """
    memories = await get_user_memory(user_id)

    if not memories:
        return ""

    stm_entries = [m for m in memories if m.memory_type == MemoryType.STM]
    ltm_entries = [m for m in memories if m.memory_type == MemoryType.LTM]

    context_parts: list[str] = []

    if ltm_entries:
        context_parts.append("=== Long-Term Memory (Important Facts) ===")
        for entry in ltm_entries:
            context_parts.append(f"  • {entry.content} [significance: {entry.significance_score}]")

    if stm_entries:
        context_parts.append("=== Short-Term Memory (Recent Interactions) ===")
        for entry in stm_entries[:settings.max_stm_entries]:  # Respect limit
            context_parts.append(f"  • {entry.content}")

    return "\n".join(context_parts)
