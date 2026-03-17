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
    try:
        # Extract explicit filters from the request if provided
        explicit_filters = req.filters.model_dump(exclude_none=True) if req.filters else None
        
        # Pass the clean/redacted query from guardrails and explicit filters into intent parser
        intent_result = await intent_agent.parse(clean_query, filters=explicit_filters)
    except Exception as exc:
        log.error("[recommend_logic] IntentAgent failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Intent agent error: {exc}")

    intent  = intent_result.intent
    courses = intent_result.courses

    if not courses:
        log.warning("[recommend_logic] No courses found for query=%r", req.query)
        raise HTTPException(status_code=404, detail="No matching courses found for this query.")

    # 3. Parallel: skill gap + career alignment
    try:
        skill_gap_task = skill_gap_agent.analyse(intent.level, courses)
        career_task    = career_agent.align(intent.career_goal, courses)
        gap_result, career_result = await asyncio.gather(skill_gap_task, career_task)
    except Exception as exc:
        log.error("[recommend_logic] Parallel agent step failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Analysis agent error: {exc}")

    # Sequencer (async)
    try:
        learning_path = await sequencer.sequence(intent.career_goal, courses)
    except Exception as exc:
        log.error("[recommend_logic] CourseSequencer failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Sequencer agent error: {exc}")

    # 4. Advisor
    try:
        rec_result = await advisor_agent.advise(
            topic=intent.topic,
            level=intent.level,
            career_goal=intent.career_goal,
            learning_path=learning_path.ordered_names,
            missing_skills=gap_result.missing_skills,
            career_track=career_result.career_track,
            alignment_reason=career_result.alignment_reason,
        )
    except Exception as exc:
        log.error("[recommend_logic] AdvisorAgent failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Advisor agent error: {exc}")

    elapsed = time.perf_counter() - t_start
    log.info("[recommend_logic] DONE | elapsed=%.2fs", elapsed)

    # 5. Build response
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
