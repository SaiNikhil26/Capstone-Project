"""
test_intent_agent.py

Standalone tester for the IntentAgent.
Runs 4 student queries through the full two-tool pipeline
(extract_intent → search_courses) and prints structured results.

Usage:
    cd "c:\\Users\\Administrator\\FDE Training\\Capstone_Project"
    python test_intent_agent.py
"""

import asyncio
import sys
import os

# Load .env BEFORE any openai-agents SDK import so the trace
# exporter can read OPENAI_API_KEY at initialisation time.
from dotenv import load_dotenv
load_dotenv()

sys.path.append(".")

from app_agents.intent_agent import IntentAgent

agent = IntentAgent()

# ── Test queries ──────────────────────────────────────────────────────────────

QUERIES = [
    {
        "label": "Test 1 — Beginner with career goal",
        "query": "I'm a complete beginner and I want to learn machine learning to become a data scientist.",
    },
    {
        "label": "Test 2 — Intermediate, specific topic",
        "query": "I already know Python basics and want to learn deep learning and neural networks.",
    },
    {
        "label": "Test 3 — Career-oriented, no level stated",
        "query": "What courses should I take to become an AI engineer?",
    },
    {
        "label": "Test 4 — Natural language with topic keywords",
        "query": "I want to understand how financial markets, investments, and global economic systems work.",
    },
]


# ── Pretty printer ────────────────────────────────────────────────────────────

def print_separator(label: str) -> None:
    print("\n" + "=" * 65)
    print(f"  {label}")
    print("=" * 65)


def print_intent(intent) -> None:
    print(f"  Topic       : {intent.topic}")
    print(f"  Level       : {intent.level}")
    print(f"  Career Goal : {intent.career_goal}")
    print(f"  Keywords    : {', '.join(intent.keywords)}")
    print(f"  Search Query: {intent.search_query}")


def print_courses(courses: list[dict]) -> None:
    if not courses:
        print("  (no courses returned)")
        return
    for i, c in enumerate(courses, 1):
        print(
            f"  {i:>2}. [{c.get('course_id', '?')}] {c.get('course_name', 'N/A')}"
        )
        print(
            f"       {c.get('organization', '')} | "
            f"{c.get('difficulty', '')} | "
            f"Rating: {c.get('rating', 'N/A')}"
        )
        skills = c.get("skills", "") or ""
        print(f"       Skills: {skills[:80]}{'...' if len(skills) > 80 else ''}")


# ── Runner ────────────────────────────────────────────────────────────────────

async def run_tests() -> None:
    for test in QUERIES:
        print_separator(test["label"])
        print(f"\n  Query: \"{test['query']}\"\n")

        try:
            result = await agent.parse(test["query"])

            print("  --- Parsed Intent ---")
            print_intent(result.intent)

            print(f"\n  --- Retrieved Courses ({len(result.courses)}) ---")
            print_courses(result.courses)

        except Exception as exc:
            print(f"  ERROR: {exc}")

    print("\n" + "=" * 65)
    print("  All tests complete")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
