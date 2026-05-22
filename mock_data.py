"""
Mock data seeder for the HR Multi-Agent Router.

Populates the database with sample memory entries and runs
example requests through the pipeline for demonstration and testing.
"""

import asyncio
import logging
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)



SAMPLE_MEMORIES = [
    # User 001 — Engineering Manager in New York
    {"user_id": "user_001", "content": "I am a manager in the engineering department"},
    {"user_id": "user_001", "content": "I am based in the New York office"},
    {"user_id": "user_001", "content": "I prefer morning meetings before 11 AM"},
    {"user_id": "user_001", "content": "My team has 8 direct reports"},
    # User 002 — HR Intern, remote
    {"user_id": "user_002", "content": "I am an intern in the HR department"},
    {"user_id": "user_002", "content": "I work from home most days"},
    {"user_id": "user_002", "content": "I started last month and am still on probation"},
    # User 003 — Finance Director
    {"user_id": "user_003", "content": "I am a director in the finance department"},
    {"user_id": "user_003", "content": "I am based in the San Francisco office"},
]


SAMPLE_REQUESTS = [
    {"user_id": "user_001", "request_text": "Schedule a team standup for tomorrow at 9am"},
    {"user_id": "user_001", "request_text": "I need to take PTO next Friday"},
    {"user_id": "user_002", "request_text": "What is the dress code policy?"},
    {"user_id": "user_002", "request_text": "Can I work from home on Wednesdays?"},
    {"user_id": "user_003", "request_text": "I need to book a conference room for a budget review"},
    {"user_id": "user_003", "request_text": "How many vacation days do I have left?"},
    {"user_id": "user_003", "request_text": "help"},  # Ambiguous — should trigger clarification
]


async def seed_database():
    """Seed the database with sample memory entries and run example requests."""
    from database import init_db
    from memory import store_memory
    from agents.graph import run_pipeline

    # Initialize DB
    await init_db()
    print("\n" + "=" * 60)
    print("  HR MULTI-AGENT ROUTER — Database Seeder")
    print("=" * 60)

    # Seed memory entries
    print("\n--- Seeding Memory Entries ---\n")
    for mem in SAMPLE_MEMORIES:
        entry = await store_memory(mem["user_id"], mem["content"])
        marker = "LTM" if entry.memory_type.value == "ltm" else "STM"
        print(f"  [{marker}] {entry.significance_score:.2f} | {mem['user_id']} | {mem['content']}")

    print(f"\n  Total: {len(SAMPLE_MEMORIES)} memory entries seeded.")

    # Run sample requests through the pipeline
    print("\n--- Running Sample Requests ---\n")
    for req in SAMPLE_REQUESTS:
        result = await run_pipeline(req["user_id"], req["request_text"])
        intent = result["intent"]
        confidence = result["confidence"]
        agent = result["sub_agent"]
        print(f"  [{intent:>14}] conf={confidence:.2f} | {agent:>20} | {req['request_text']}")

    print(f"\n  Total: {len(SAMPLE_REQUESTS)} requests processed.")
    print(f"  Audit log entries created: {len(SAMPLE_REQUESTS)}")

    print("\n" + "=" * 60)
    print("  Seeding complete! Database is ready for testing.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(seed_database())
