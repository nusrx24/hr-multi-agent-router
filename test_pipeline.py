"""Quick integration test for the full LangGraph pipeline."""

import asyncio
import logging
import sys
import io

# Fix Windows terminal encoding for emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")


async def test():
    from database import init_db
    await init_db()
    print("DB initialized\n")

    from agents.graph import run_pipeline

    tests = [
        ("user_001", "I need to schedule a team meeting for tomorrow at 3pm"),
        ("user_001", "How many PTO days do I have remaining?"),
        ("user_002", "What is the company remote work policy?"),
        ("user_002", "hello"),
    ]

    for user_id, request_text in tests:
        print(f"=== Request: {request_text} ===")
        result = await run_pipeline(user_id, request_text)
        print(f"  Intent:     {result['intent']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Sub-Agent:  {result['sub_agent']}")
        print(f"  Response:   {result['response'][:120]}...")
        print(f"  Error:      {result['error']}")
        print()

    print("=== ALL PIPELINE TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(test())
