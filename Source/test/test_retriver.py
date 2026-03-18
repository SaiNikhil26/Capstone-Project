import sys
sys.path.append(".")

from retrieval.hybrid_retriever import hybrid_search
from logger import get_logger

log = get_logger("test_retriever")

def run_tests():

    # ── Test 1: Semantic query ──────────────────────────
    print("\n" + "="*60)
    print("Test 1: Semantic query")
    print("="*60)
    query = "I want to learn Machine Learning"
    log.info(f"Running test 1 | query: '{query}'")

    results = hybrid_search(query)
    for r in results:
        print(f"  {r.get('course_id')} | {r.get('course_name')}")
        print(f"           Difficulty: {r.get('difficulty')} | Rating: {r.get('rating')}")
        print(f"           Skills: {r.get('skills')[:80]}...")
        print()

    # ── Test 2: Keyword query ───────────────────────────
    print("\n" + "="*60)
    print("Test 2: Keyword query")
    print("="*60)
    query = "Python pandas NumPy data science"
    log.info(f"Running test 2 | query: '{query}'")

    results = hybrid_search(query)
    for r in results:
        print(f"  {r.get('course_id')} | {r.get('course_name')}")
        print(f"           Difficulty: {r.get('difficulty')} | Rating: {r.get('rating')}")
        print(f"           Skills: {r.get('skills')[:80]}...")
        print()

    # ── Test 3: Career-oriented query ──────────────────
    print("\n" + "="*60)
    print("Test 3: Career-oriented query")
    print("="*60)
    query = "I want to become a data scientist"
    log.info(f"Running test 3 | query: '{query}'")

    results = hybrid_search(query)
    for r in results:
        print(f"  {r.get('course_id')} | {r.get('course_name')}")
        print(f"           Difficulty: {r.get('difficulty')} | Rating: {r.get('rating')}")
        print(f"           Skills: {r.get('skills')[:80]}...")
        print()

    # ── Test 4: With difficulty filter ─────────────────
    print("\n" + "="*60)
    print("Test 4: With difficulty filter — Beginner only")
    print("="*60)
    query = "deep learning neural networks"
    log.info(f"Running test 4 | query: '{query}' | filter: Beginner")

    results = hybrid_search(
        query,
        filters={"difficulty": "Beginner"}
    )
    for r in results:
        print(f"  {r.get('course_id')} | {r.get('course_name')}")
        print(f"           Difficulty: {r.get('difficulty')} | Rating: {r.get('rating')}")
        print(f"           Skills: {r.get('skills')[:80]}...")
        print()

    # ── Test 5: With rating filter ──────────────────────
    print("\n" + "="*60)
    print("Test 5: With min_rating filter — 4.8+")
    print("="*60)
    query = "cloud computing AWS"
    log.info(f"Running test 5 | query: '{query}' | filter: min_rating=4.8")

    results = hybrid_search(
        query,
        filters={"min_rating": 4.8}
    )
    for r in results:
        print(f"  {r.get('course_id')} | {r.get('course_name')}")
        print(f"           Difficulty: {r.get('difficulty')} | Rating: {r.get('rating')}")
        print(f"           Skills: {r.get('skills')[:80]}...")
        print()

    # ── Test 6: Combined filters ────────────────────────
    print("\n" + "="*60)
    print("Test 6: Combined filters — Beginner + min_rating 4.7")
    print("="*60)
    query = "artificial intelligence for beginners"
    log.info(f"Running test 6 | query: '{query}' | filters: Beginner + 4.7")

    results = hybrid_search(
        query,
        filters={
            "difficulty": "Beginner",
            "min_rating": 4.7
        }
    )
    for r in results:
        print(f"  {r.get('course_id')} | {r.get('course_name')}")
        print(f"           Difficulty: {r.get('difficulty')} | Rating: {r.get('rating')}")
        print(f"           Skills: {r.get('skills')[:80]}...")
        print()

    print("\n" + "="*60)
    print("All tests complete")
    print("="*60)


if __name__ == "__main__":
    run_tests()