"""
test/trace_pipeline.py

Comprehensive trace script to capture intermediate outputs of every component:
- Vector Retrieval (Semantic)
- Keyword Retrieval (BM25)
- RRF Fusion logic
- Cross-Encoder Reranking
- Intent, SkillGap, Career, Sequencer, and Advisor Agent outputs.

Outputs are saved to trace_output.txt.
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

# Ensure environment is loaded
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import OpenAIEmbeddings
from config import EMBEDDING_MODEL
from logger import get_logger

# Import internal retrieval functions
from retrieval.hybrid_retriever import (
    semantic_search,
    keyword_search,
    reciprocal_rank_fusion,
    fetch_parent_docs,
    rerank_courses
)

# Import agents/logic
from api.core.recommend_logic import (
    intent_agent,
    skill_gap_agent,
    career_agent,
    sequencer,
    advisor_agent,
    guardrail_checker
)

log = get_logger("trace_pipeline")

async def trace_pipeline(query: str, filters: dict = None):
    output_file = "trace_output.txt"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write(f"FULL PIPELINE TRACE FOR QUERY: '{query}'\n")
        f.write(f"FILTERS: {filters}\n")
        f.write("="*80 + "\n\n")

        # 1. Guardrails
        f.write("--- [STAGE 1: GUARDRAILS] ---\n")
        clean_query = await guardrail_checker.validate(query)
        f.write(f"Input Query: {query}\n")
        f.write(f"Cleaned/Redacted Query: {clean_query}\n\n")

        # 2. Intent Analysis
        f.write("--- [STAGE 2: INTENT ANALYSIS] ---\n")
        intent_res = await intent_agent.parse(clean_query, filters=filters)
        f.write(f"[2.1] Extracting Intent...\n")
        f.write(json.dumps(intent_res.intent.model_dump(), indent=2) + "\n")
        search_query = intent_res.intent.search_query
        f.write(f"Optimized Search Query: {search_query}\n\n")

        # 3. Retrieval Components
        f.write("--- [STAGE 3: RETRIEVAL COMPONENTS] ---\n")
        embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
        
        # Semantic
        semantic_docs = semantic_search(search_query, embeddings, filters)
        semantic_names = []
        for d in semantic_docs:
            name = d.metadata.get("course_name") or d.metadata.get("course_id")
            if not name and "Course: " in d.page_content:
                 name = d.page_content.split("by")[0].replace("Course:", "").strip()
            semantic_names.append(name or f"Chunk ID: {d.metadata.get('_id', 'unknown')}")
            
        f.write(f"[3.1] Vector Retrieval (Semantic) Hits:\n")
        for i, val in enumerate(semantic_names, 1): f.write(f"  {i}. {val}\n")
        f.write("\n")

        # Keyword
        keyword_docs = keyword_search(search_query)
        keyword_names = [d.metadata.get("course_name") or d.metadata.get("course_id") for d in keyword_docs]
        f.write(f"[3.2] Keyword Retrieval (BM25) Hits:\n")
        for i, val in enumerate(keyword_names, 1): f.write(f"  {i}. {val}\n")
        f.write("\n")

        # RRF Fusion
        fused_docs = reciprocal_rank_fusion(semantic_docs, keyword_docs)
        fused_names = [d.metadata.get("course_name") or d.metadata.get("course_id") for d in fused_docs]
        fused_ids = [d.metadata.get("parent_id") or d.metadata.get("course_id") for d in fused_docs]
        f.write(f"[3.3] RRF Fusion (Combined Ranks):\n")
        for i, val in enumerate(fused_names, 1): f.write(f"  {i}. {val} (ID: {fused_ids[i-1]})\n")
        f.write("\n")

        # Parent Fetch & UI Filters
        parent_docs = fetch_parent_docs(fused_docs, filters)
        parent_names = [d.get("course_name") for d in parent_docs]
        f.write(f"[3.4] Parent Fetch & UI Filter Results (Pre-Rerank):\n")
        for i, val in enumerate(parent_names, 1): f.write(f"  {i}. {val}\n")
        f.write("\n")

        # Cross-Encoder Reranker
        reranked_docs = rerank_courses(search_query, parent_docs)
        f.write(f"[3.5] Cross-Encoder Reranker (MiniLM-L-12) Final Sorted List:\n")
        for i, d in enumerate(reranked_docs, 1):
            name = d.get('course_name')
            score = d.get('_rerank_score', 0.0)
            f.write(f"  {i}. [Score: {score: .4f}] {name}\n")
        f.write("\n")

        # 4. Agent Reasoning
        f.write("--- [STAGE 4: AGENT REASONING] ---\n")
        
        # Skill Gap Agent
        gap_res = await skill_gap_agent.analyse(intent_res.intent.level, reranked_docs)
        f.write(f"[4.1] Skill Gap Agent Result:\n")
        f.write(json.dumps(gap_res.model_dump(), indent=2) + "\n\n")

        # Career Agent
        career_res = await career_agent.align(intent_res.intent.career_goal, reranked_docs)
        f.write(f"[4.2] Career Agent Result:\n")
        f.write(json.dumps(career_res.model_dump(), indent=2) + "\n\n")

        # Sequencer
        path_res = await sequencer.sequence(intent_res.intent.career_goal, reranked_docs)
        f.write(f"[4.3] Sequencer Result (Themed Path):\n")
        for stage in path_res.stages:
            scnames = [c.get('course_name') for c in stage.courses]
            f.write(f"  - {stage.stage}: {', '.join(scnames)}\n")
        f.write("\n")

        # Advisor Agent
        adv_res = await advisor_agent.advise(
            topic=intent_res.intent.topic,
            level=intent_res.intent.level,
            career_goal=intent_res.intent.career_goal,
            learning_path=path_res.ordered_names,
            missing_skills=gap_res.missing_skills,
            career_track=career_res.career_track,
            alignment_reason=career_res.alignment_reason
        )
        f.write(f"[4.4] Learning Advisor Agent Result:\n")
        f.write(f"Summary: {adv_res.summary}\n")
        f.write(f"Tips:\n")
        for tip in adv_res.tips: f.write(f"  * {tip}\n")
        f.write("\n")

        f.write("="*80 + "\n")
        f.write("END OF TRACE\n")
        f.write("="*80 + "\n")

    print(f"Pipeline trace completed. Output saved to {output_file}")

if __name__ == "__main__":
    query = "I want to learn Deep Learning using Python, but I am a beginner."
    asyncio.run(trace_pipeline(query))
