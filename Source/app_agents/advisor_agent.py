"""
app_agents/advisor_agent.py

LearningAdvisorAgent — produces the final advisory message for the student,
synthesising intent, skill gaps, career alignment, and the learning path.

Single-tool pipeline:
  report_recommendation — output summary + ordered path + tips
"""

from __future__ import annotations

import json
import time
import sys
import os

from agents import Agent, Runner
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LLM_MODEL
from logger import get_logger
from app_agents.tools import report_recommendation
from api.utils.token_utils import count_tokens

log = get_logger("advisor_agent")


# ─────────────────────────────────────────────────────────────────────────────
# Output schema
# ─────────────────────────────────────────────────────────────────────────────

class RecommendationResult(BaseModel):
    summary:       str
    learning_path: list[str]   # ordered course names
    tips:          list[str]
    usage:         dict = {}   # {input, output, model}


# ─────────────────────────────────────────────────────────────────────────────
# Agent definition
# ─────────────────────────────────────────────────────────────────────────────

advisor_agent = Agent(
    name="LearningAdvisorAgent",
    model=LLM_MODEL,
    instructions="""
You are a friendly academic learning advisor for a university course discovery system.

You will receive a structured summary containing:
  - The student's academic topic, level, and career goal.
  - A structured **Learning Path** organized into **Themed Milestones** (stages).
  - Detected skill gaps and career alignment notes.

Your job is to call report_recommendation EXACTLY ONCE to produce the final student-facing advice.

─── Rules for the summary ──────────────────────────────────────────
- Tone: Encouraging, professional, and student-centric.
- **Reference Milestones**: Explicitly mention the themed milestones (e.g., "We'll start with your 'Foundational Tools'...") to help the student visualize their journey.
- Contextualize: Connect the recommendations to their career goal and acknowledge how the plan addresses their specific skill gaps.
- Length: 3-5 high-impact sentences. Avoid generic corporate speak.

─── Rules for the learning_path & tips ───────────────────────────
- learning_path: Return a flat, ordered list of course names extracted from provide stages.
- tips: 2-3 short, actionable, and specific technical tips.
─────────────────────────────────────────────────────────────────
Always call report_recommendation. Never respond in plain text.
""",
    tools=[report_recommendation],
)

log.info("[Agent:created] LearningAdvisorAgent | model=%s", LLM_MODEL)


# ─────────────────────────────────────────────────────────────────────────────
# Class wrapper
# ─────────────────────────────────────────────────────────────────────────────

class LearningAdvisorAgent:
    """
    Usage:
        agent = LearningAdvisorAgent()
        result: RecommendationResult = await agent.advise(context)
    """

    def __init__(self) -> None:
        log.debug("[LearningAdvisorAgent] initialised")

    async def advise(
        self,
        topic:           str,
        level:           str,
        career_goal:     str,
        stages:          list[any],      # list of LearningPathStage objects
        missing_skills:  list[str],
        career_track:    str,
        alignment_reason: str,
    ) -> RecommendationResult:
        log.info("[LearningAdvisorAgent:advise] START | topic=%r | stages=%d", topic, len(stages))

        prompt = self._build_prompt(
            topic, level, career_goal, stages,
            missing_skills, career_track, alignment_reason,
        )

        t0 = time.perf_counter()
        result = await Runner.run(advisor_agent, prompt)
        elapsed = time.perf_counter() - t0

        log.info("[LearningAdvisorAgent:advise] finished | elapsed=%.2fs", elapsed)

        rec = self._extract_result(result)

        # Estimate tokens
        input_tokens  = count_tokens(prompt, LLM_MODEL)
        output_tokens = count_tokens(result.final_output or str(rec.model_dump()), LLM_MODEL)
        rec.usage = {"agent": "AdvisorAgent", "input": input_tokens, "output": output_tokens, "model": LLM_MODEL}

        log.info(
            "[LearningAdvisorAgent:advise] END | summary_len=%d | tokens=%d",
            len(rec.summary), input_tokens + output_tokens
        )
        return rec

    def _build_prompt(
        self,
        topic, level, career_goal, stages,
        missing_skills, career_track, alignment_reason,
    ) -> str:
        # Format the structured path for the prompt
        path_blueprint = []
        for i, s in enumerate(stages):
            stage_name = getattr(s, "stage", "Stage")
            courses = getattr(s, "courses", [])
            course_list = "\n".join([f"    - {c.get('course_name')}" for c in courses])
            path_blueprint.append(f"  Stage {i+1}: {stage_name}\n{course_list}")
        
        blueprint_str = "\n".join(path_blueprint)
        gaps_str = ", ".join(missing_skills) if missing_skills else "None detected"

        return (
            f"STUDENT CONTEXT:\n"
            f"Topic: {topic}\n"
            f"Current Level: {level}\n"
            f"Career Goal: {career_goal}\n\n"
            f"CURRICULUM ANALYSIS:\n"
            f"Career Alignment: {career_track} — {alignment_reason}\n"
            f"Detected Skill Gaps: {gaps_str}\n\n"
            f"STRUCTURED LEARNING PATH:\n{blueprint_str}\n\n"
            "INSTRUCTIONS:\n"
            "Synthesise this into a final recommendation. Call report_recommendation "
            "with a summary that highlights the milestones, the learning_path (flat list), and study tips."
        )

    def _extract_result(self, result) -> RecommendationResult:
        for item in result.new_items:
            if type(item).__name__ == "ToolCallOutputItem":
                parsed = self._safe_json(getattr(item, "output", ""))
                if parsed and "summary" in parsed:
                    return RecommendationResult(**parsed)

        log.warning("[LearningAdvisorAgent] tool not called — returning fallback")
        return RecommendationResult(
            summary="Here are your personalised course recommendations.",
            learning_path=learning_path[:5] if learning_path else [],
            tips=["Start with the foundational courses first."],
        )

    def _safe_json(self, raw) -> dict | None:
        try:
            return json.loads(str(raw))
        except Exception:
            return None
