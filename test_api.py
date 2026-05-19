"""Test all 5 API endpoints against the running server."""

import httpx
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"


def main():
    # 1. Health
    print("=== 1. GET /health ===")
    r = httpx.get(f"{BASE}/api/v1/health")
    print(f"  Status: {r.status_code}")
    data = r.json()
    print(f"  DB: {data['database']}, Status: {data['status']}")
    assert r.status_code == 200

    # 2. POST /request — scheduling
    print("\n=== 2. POST /request (scheduling) ===")
    r = httpx.post(
        f"{BASE}/api/v1/request",
        json={"user_id": "user_001", "request_text": "Schedule a team meeting for tomorrow at 2pm"},
        timeout=30,
    )
    print(f"  Status: {r.status_code}")
    data = r.json()
    print(f"  Intent: {data['intent']}, Confidence: {data['confidence']}, Agent: {data['sub_agent']}")
    print(f"  Response: {data['response'][:100]}...")
    assert r.status_code == 200

    # 3. POST /request — leave
    print("\n=== 3. POST /request (leave) ===")
    r = httpx.post(
        f"{BASE}/api/v1/request",
        json={"user_id": "user_001", "request_text": "How many sick days do I have remaining?"},
        timeout=30,
    )
    print(f"  Status: {r.status_code}")
    data = r.json()
    print(f"  Intent: {data['intent']}, Confidence: {data['confidence']}, Agent: {data['sub_agent']}")
    assert r.status_code == 200

    # 4. GET /audit
    print("\n=== 4. GET /audit ===")
    r = httpx.get(f"{BASE}/api/v1/audit", params={"page": 1, "limit": 10})
    print(f"  Status: {r.status_code}")
    data = r.json()
    print(f"  Total entries: {data['total']}")
    for entry in data["entries"]:
        print(f"    - [{entry['intent']}] conf={entry['confidence']} | {entry['request_text'][:50]}")
    assert r.status_code == 200
    assert data["total"] >= 2

    # 5. GET /memory/{user_id}
    print("\n=== 5. GET /memory/user_001 ===")
    r = httpx.get(f"{BASE}/api/v1/memory/user_001")
    print(f"  Status: {r.status_code}")
    data = r.json()
    print(f"  STM entries: {len(data['stm'])}")
    print(f"  LTM entries: {len(data['ltm'])}")
    for m in data["stm"][:3]:
        print(f"    STM: {m['content'][:60]}... (score={m['significance_score']})")
    for m in data["ltm"][:3]:
        print(f"    LTM: {m['content'][:60]}... (score={m['significance_score']})")
    assert r.status_code == 200

    # 6. DELETE /memory/{user_id}
    print("\n=== 6. DELETE /memory/user_001 (clear STM) ===")
    r = httpx.delete(f"{BASE}/api/v1/memory/user_001")
    print(f"  Status: {r.status_code}")
    data = r.json()
    print(f"  Message: {data['message']}")
    assert r.status_code == 200

    # Verify STM is cleared
    r = httpx.get(f"{BASE}/api/v1/memory/user_001")
    data = r.json()
    print(f"  After clear — STM: {len(data['stm'])}, LTM: {len(data['ltm'])}")

    print("\n=== ALL 5 ENDPOINT TESTS PASSED ===")


if __name__ == "__main__":
    main()
