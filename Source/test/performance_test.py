import time
import httpx
import asyncio
import statistics
import json

# --- Config ---
GATEWAY_URL = "http://localhost:8080/recommend"
CONCURRENT_REQUESTS = 1      # Set to >1 for load testing
TOTAL_REQUESTS = 5           # Total requests to run
SAMPLE_QUERIES = [
    "I want to learn Deep Learning with Python as a beginner",
    "I'm looking for advanced courses on Cloud Computing and AWS",
    "Find me courses on Data Science foundations and Math",
    "I want to become a Cybersercurity Analyst",
    "How to build a web app using React and Node.js?"
]

async def hit_api(client: httpx.AsyncClient, query: str, req_id: int):
    payload = {
        "query": query,
        "filters": None
    }
    
    t0 = time.perf_counter()
    try:
        response = await client.post(GATEWAY_URL, json=payload)
        t1 = time.perf_counter()
        
        elapsed = t1 - t0
        status = response.status_code
        
        if status == 200:
            data = response.json()
            # Extract server-side timing if available in message or headers
            # Agent message is usually "Recommendations generated in 4.2s."
            msg = data.get("message", "")
            agent_time = 0.0
            if "in " in msg and "s." in msg:
                try:
                    agent_time = float(msg.split("in ")[1].replace("s.", ""))
                except: pass
            
            # Gateway time from header (e.g., "4.35s")
            gateway_time_str = response.headers.get("X-Gateway-Time", "0.00s").replace("s", "")
            gateway_time = float(gateway_time_str)
            
            return {
                "id": req_id,
                "status": status,
                "total_time": elapsed,
                "gateway_time": gateway_time,
                "agent_time": agent_time,
                "error": None
            }
        else:
            return {
                "id": req_id,
                "status": status,
                "total_time": elapsed,
                "error": response.text
            }
            
    except Exception as e:
        return {
            "id": req_id,
            "status": "ERROR",
            "total_time": time.perf_counter() - t0,
            "error": str(e)
        }

async def run_test():
    print(f"=== Starting Performance Test ===")
    print(f"Target: {GATEWAY_URL}")
    print(f"Total Requests: {TOTAL_REQUESTS}")
    print(f"Concurrent: {CONCURRENT_REQUESTS}")
    print("-" * 40)

    results = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        # We run in chunks of CONCURRENT_REQUESTS
        for i in range(0, TOTAL_REQUESTS, CONCURRENT_REQUESTS):
            tasks = []
            for j in range(CONCURRENT_REQUESTS):
                if i + j >= TOTAL_REQUESTS: break
                query = SAMPLE_QUERIES[(i + j) % len(SAMPLE_QUERIES)]
                tasks.append(hit_api(client, query, i + j + 1))
            
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            
            for r in batch_results:
                if r['status'] == 200:
                    print(f"Req {r['id']}: SUCCESS | Total: {r['total_time']:.2f}s | Agent: {r['agent_time']:.2f}s")
                else:
                    print(f"Req {r['id']}: FAILED ({r['status']}) | {r['error'][:50]}...")

    # --- Metrics ---
    successes = [r for r in results if r['status'] == 200]
    if not successes:
        print("No successful requests to calculate metrics.")
        return

    total_times = [r['total_time'] for r in successes]
    agent_times = [r['agent_time'] for r in successes]
    gateway_times = [r['gateway_time'] for r in successes]

    print("\n" + "="*40)
    print("      PERFORMANCE METRICS SUMMARY")
    print("="*40)
    print(f"Requests: {len(results)} Total, {len(successes)} Success")
    print("-" * 40)
    print(f"{'Metric':<15} | {'Avg':<8} | {'Min':<8} | {'Max':<8} | {'P95':<8}")
    print("-" * 40)
    
    def print_row(label, data):
        avg = statistics.mean(data)
        mn = min(data)
        mx = max(data)
        # Simple P95 for small samples
        p95 = sorted(data)[int(len(data)*0.95)] if len(data) > 0 else 0
        print(f"{label:<15} | {avg:<8.2f} | {mn:<8.2f} | {mx:<8.2f} | {p95:<8.2f}")

    print_row("Total Latency", total_times)
    print_row("Gateway Time", gateway_times)
    print_row("Agent Reasoning", agent_times)
    
    print("-" * 40)
    overhead = statistics.mean(total_times) - statistics.mean(agent_times)
    print(f"Average Network/IO Overhead: {overhead:.2f}s")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(run_test())
