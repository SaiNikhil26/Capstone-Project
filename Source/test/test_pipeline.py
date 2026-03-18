"""
test/test_pipeline.py

End-to-end test for the course recommendation pipeline.
Verifies Guardrails -> IntentAgent -> Retrieval -> Parallel Agents -> Advisor.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

# Ensure environment is loaded
from dotenv import load_dotenv
load_dotenv()

from api.core.recommend_logic import generate_recommendations
from api.schemas import RecommendRequest, FiltersModel


async def run_test(query: str, filters: dict = None):
    print("\n" + "="*80)
    print(f"TESTING QUERY: {query}")
    if filters:
        print(f"FILTERS: {filters}")
    print("="*80)
    
    req = RecommendRequest(
        query=query,
        filters=FiltersModel(**filters) if filters else None
    )
    
    try:
        start_time = asyncio.get_event_loop().time()
        res = await generate_recommendations(req)
        end_time = asyncio.get_event_loop().time()
        
        print(f"\n[SUCCESS] Response received in {end_time - start_time:.2f}s")
        
        print(f"\n--- INTENT ---")
        print(f"Topic:    {res.intent.topic}")
        print(f"Level:    {res.intent.level}")
        print(f"Goal:     {res.intent.career_goal}")
        print(f"Keywords: {res.intent.keywords}")
        
        print(f"\n--- RETRIEVAL (Top 5 of {len(res.courses)}) ---")
        for i, c in enumerate(res.courses[:5]):
            print(f"{i+1}. [{c.difficulty}] {c.course_name} ({c.organization}) - Rating: {c.rating}")
            
        print(f"\n--- SKILL GAP ---")
        print(f"Has Gaps? {res.skill_gap.has_gaps}")
        print(f"Missing:  {', '.join(res.skill_gap.missing_skills)}")
        
        print(f"\n--- CAREER ALIGNMENT ---")
        print(f"Track:    {res.career_alignment.career_track}")
        print(f"Reason:   {res.career_alignment.alignment_reason[:200]}...")
        
        print(f"\n--- LEARNING PATH ---")
        for stage in res.learning_path:
            print(f"Stage: {stage.stage}")
            for c in stage.courses:
                print(f"  - {c.course_name}")
                
        print(f"\n--- ADVISOR RECOMMENDATION ---")
        print(f"Summary: {res.recommendation.summary[:300]}...")
        print(f"\nTips:")
        for tip in res.recommendation.tips:
            print(f"- {tip}")
            
    except Exception as e:
        print(f"\n[FAILED] Pipeline crashed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    test_cases = [
        {
            "query": "I want to learn Deep Learning using Python, but I am a beginner.",
            "filters": None
        },
        {
            "query": "Advanced React development for experienced engineers.",
            "filters": {
                "difficulty": "Advanced",
                "organization": "Meta"
            }
        },
        {
            "query": "My name is John Doe and I want to learn about Financial Markets. My email is john@example.com",
            "filters": None
        }
    ]
    
    for case in test_cases:
        await run_test(case["query"], case["filters"])

if __name__ == "__main__":
    asyncio.run(main())
