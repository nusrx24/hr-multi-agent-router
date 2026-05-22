"""Quick test for dashboard and API endpoints."""
import httpx
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"

# Test dashboard
r = httpx.get(f"{BASE}/dashboard/")
print(f"Dashboard: {r.status_code}, Size: {len(r.content)} bytes")
assert r.status_code == 200
assert "HR Multi-Agent Router" in r.text
print("  -> Dashboard loads correctly!")

# Test redirect from root
r = httpx.get(f"{BASE}/", follow_redirects=False)
print(f"\nRoot redirect: {r.status_code}, Location: {r.headers.get('location', 'N/A')}")
assert r.status_code == 307

# Test health
r = httpx.get(f"{BASE}/api/v1/health")
print(f"\nHealth: {r.status_code} -> {r.json()['status']}")
assert r.status_code == 200

# Test a request through the pipeline
r = httpx.post(f"{BASE}/api/v1/request", json={
    "user_id": "ui_test",
    "request_text": "Schedule a meeting for tomorrow at 3pm"
}, timeout=30)
data = r.json()
print(f"\nPipeline: {r.status_code}")
print(f"  Intent: {data['intent']}, Confidence: {data['confidence']}, Agent: {data['sub_agent']}")
assert r.status_code == 200
assert data["intent"] == "scheduling"

# Test info endpoint
r = httpx.get(f"{BASE}/api/v1/info")
print(f"\nAPI Info: {r.status_code}")
assert r.status_code == 200
assert "dashboard" in r.json()

print("\n=== ALL TESTS PASSED ===")
