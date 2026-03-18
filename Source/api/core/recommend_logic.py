"""
api/core/recommend_logic.py

Core business logic for generating course recommendations.
Orchestrates the execution of all agents.
"""

import asyncio
import time
from fastapi import HTTPException

# Ensure environment is loaded before agents (trace exporter fix)
from dotenv import load_dotenv
load_dotenv()

from logger import get_logger
from api.schemas import (
    RecommendRequest, RecommendResponse,
    IntentSchema, SkillGapSchema,
    LearningPathStageSchema, CareerAlignmentSchema,
    RecommendationSchema,
)
from api.utils.helpers import to_course_schema
from guardrails.validator import GuardrailValidator

from app_agents.intent_agent    import IntentAgent
from app_agents.skill_gap_agent import SkillGapAgent
from app_agents.career_agent    import CareerAgent
from app_agents.sequencer       import CourseSequencer
from app_agents.advisor_agent   import LearningAdvisorAgent

log = get_logger("recommend_logic")

# ─────────────────────────────────────────────────────────────────────────────
# Agent singletons
# ─────────────────────────────────────────────────────────────────────────────
intent_agent      = IntentAgent()
skill_gap_agent   = SkillGapAgent()
career_agent      = CareerAgent()
sequencer         = CourseSequencer()
advisor_agent     = LearningAdvisorAgent()
guardrail_checker = GuardrailValidator()


async def generate_recommendations(req: RecommendRequest) -> RecommendResponse:
    """
    Execute the full agent pipeline to generate recommendations.
    """
    t_start = time.perf_counter()
    log.info("[recommend_logic] START | query=%r filters=%r", req.query, req.filters)

    # 1. Validate & Redact PII (LangChain via HTTP exception to fast API)
    clean_query = await guardrail_checker.validate(req.query)

    # 2. Intent + retrieval
    explicit_filters = req.filters.model_dump(exclude_none=True) if req.filters else None
    
    try:
        # Pass the clean/redacted query from guardrails and explicit filters into intent parser
        intent_result = await intent_agent.parse(clean_query, filters=explicit_filters)
        intent  = intent_result.intent
        courses = intent_result.courses
    except Exception as exc:
        log.warning("[recommend_logic] IntentAgent failed: %s. Falling back to direct hybrid search.", exc)
        from retrieval.hybrid_retriever import hybrid_search
        
        # Fallback to direct search without LLM intent extraction
        courses = hybrid_search(clean_query, filters=explicit_filters)
        
        # Construct a dummy intent schema
        intent = IntentSchema(
            topic="General Discovery",
            level="Not specified",
            career_goal="Foundational Knowledge",
            known_skills=[],
            keywords=[clean_query],
            search_query=clean_query
        )

    if not courses:
        log.warning("[recommend_logic] No courses found for query=%r", req.query)
        raise HTTPException(status_code=404, detail="No matching courses found for this query.")

    # 3. Try Agent Pipeline (Skill Gap, Career, Sequencer, Advisor)
    try:
        # Parallel: skill gap + career alignment
        skill_gap_task = skill_gap_agent.analyse(intent.level, intent.known_skills, courses)
        career_task    = career_agent.align(intent.career_goal, courses)
        gap_result, career_result = await asyncio.gather(skill_gap_task, career_task)

        # --- Inject Bridging Courses if gaps exist ---
        if gap_result.has_gaps and gap_result.foundational_topics:
            from retrieval.hybrid_retriever import hybrid_search
            log.info("[recommend_logic] Fetching bridging courses for: %s", gap_result.foundational_topics)
            
            existing_ids = {c.get("course_id") for c in courses if c.get("course_id")}
            
            # Fetch up to 2 beginner courses per foundational topic
            for topic in gap_result.foundational_topics:
                try:
                    # Search specifically for beginner bridging material
                    topic_results = hybrid_search(topic, filters={"difficulty": "Beginner"})
                    for bc in topic_results[:2]:
                        cid = bc.get("course_id")
                        if cid and cid not in existing_ids:
                            courses.append(bc)
                            existing_ids.add(cid)
                            log.info("[recommend_logic] Added bridge course: %s", bc.get("course_name"))
                except Exception as ex:
                    log.warning("[recommend_logic] Failed to fetch bridging course for %s: %s", topic, ex)

        # Sequencer (async)
        learning_path = await sequencer.sequence(intent.career_goal, courses)

        # 4. Advisor
        rec_result = await advisor_agent.advise(
            topic=intent.topic,
            level=intent.level,
            career_goal=intent.career_goal,
            stages=learning_path.stages,
            missing_skills=gap_result.missing_skills,
            career_track=career_result.career_track,
            alignment_reason=career_result.alignment_reason,
        )

        elapsed = time.perf_counter() - t_start
        log.info("[recommend_logic] DONE | elapsed=%.2fs", elapsed)

        # 5. Build full response
        return RecommendResponse(
            intent=IntentSchema(**intent.model_dump()),
            courses=[to_course_schema(c) for c in courses],
            skill_gap=SkillGapSchema(
                has_gaps=gap_result.has_gaps,
                missing_skills=gap_result.missing_skills,
                foundational_topics=gap_result.foundational_topics,
            ),
            learning_path=[
                LearningPathStageSchema(
                    stage=stage.stage,
                    courses=[to_course_schema(c) for c in stage.courses],
                )
                for stage in learning_path.stages
            ],
            career_alignment=CareerAlignmentSchema(
                career_track=career_result.career_track,
                top_course_ids=career_result.top_course_ids,
                alignment_reason=career_result.alignment_reason,
            ),
            recommendation=RecommendationSchema(
                summary=rec_result.summary,
                learning_path=rec_result.learning_path,
                tips=rec_result.tips,
            ),
            message=f"Recommendations generated in {elapsed:.1f}s.",
        )
        
    except Exception as exc:
        log.error("[recommend_logic] Agent pipeline failed: %s. Falling back to simple course list.", exc)
        elapsed = time.perf_counter() - t_start
        
        # 6. Build Fallback Response
        # We have the courses, but reasoning failed. Return default/empty metadata.
        return RecommendResponse(
            intent=IntentSchema(**intent.model_dump()),
            courses=[to_course_schema(c) for c in courses],
            skill_gap=SkillGapSchema(
                has_gaps=False,
                missing_skills=[],
                foundational_topics=[],
            ),
            learning_path=[
                LearningPathStageSchema(
                    stage="Fallback Recommended Courses",
                    courses=[to_course_schema(c) for c in courses]
                )
            ],
            career_alignment=CareerAlignmentSchema(
                career_track=intent.career_goal or "General",
                top_course_ids=[],
                alignment_reason="Career alignment is currently unavailable due to system overhead."
            ),
            recommendation=RecommendationSchema(
                summary="Here are the top courses matching your request. (Detailed AI advice is temporarily unavailable).",
                learning_path=[],
                tips=[]
            ),
            message=f"Recommendations generated (fallback mode) in {elapsed:.1f}s."
        )
