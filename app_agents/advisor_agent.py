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

log = get_logger("advisor_agent")


# ─────────────────────────────────────────────────────────────────────────────
# Output schema
# ─────────────────────────────────────────────────────────────────────────────

class RecommendationResult(BaseModel):
    summary:       str
    learning_path: list[str]   # ordered course names
    tips:          list[str]


# ─────────────────────────────────────────────────────────────────────────────
# Agent definition
# ─────────────────────────────────────────────────────────────────────────────

advisor_agent = Agent(
    name="LearningAdvisorAgent",
    model=LLM_MODEL,
    instructions="""
You are a friendly academic learning advisor for a university course discovery system.

You will receive a structured summary of:
  - The student's topic, level, and career goal
  - Suggested learning path (ordered course names)
  - Skill gaps detected (if any)
  - Career alignment notes

Your job is to call report_recommendation EXACTLY ONCE.

─── Rules ────────────────────────────────────────────────────────
- summary: 2-3 friendly, encouraging sentences. Mention the topic,
  acknowledge any skill gaps, and reference the career goal if set.
  Keep it student-facing — no jargon.
- learning_path: use the ordered course names provided. Do not change
  the order. Include 3-5 courses.
- tips: 2-3 short, actionable study tips specific to the topic/level.
  e.g. "Start with hands-on projects early",
       "Review linear algebra basics before the ML courses".
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
        topic:         str,
        level:         str,
        career_goal:   str,
        learning_path: list[str],        # ordered course names from sequencer
        missing_skills: list[str],       # from skill gap agent
        career_track:  str,              # from career agent
        alignment_reason: str,           # from career agent
    ) -> RecommendationResult:
        log.info("[LearningAdvisorAgent:advise] START | topic=%r | level=%r", topic, level)

        prompt = self._build_prompt(
            topic, level, career_goal, learning_path,
            missing_skills, career_track, alignment_reason,
        )

        t0 = time.perf_counter()
        result = await Runner.run(advisor_agent, prompt)
        elapsed = time.perf_counter() - t0

        log.info("[LearningAdvisorAgent:advise] finished | elapsed=%.2fs", elapsed)

        rec = self._extract_result(result)
        log.info("[LearningAdvisorAgent:advise] END | path_length=%d", len(rec.learning_path))
        return rec

    def _build_prompt(
        self,
        topic, level, career_goal, learning_path,
        missing_skills, career_track, alignment_reason,
    ) -> str:
        path_str = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(learning_path[:5]))
        gaps_str = ", ".join(missing_skills) if missing_skills else "None detected"

        return (
            f"Topic: {topic}\n"
            f"Level: {level}\n"
            f"Career goal: {career_goal}\n"
            f"Career track: {career_track} — {alignment_reason}\n"
            f"Skill gaps: {gaps_str}\n"
            f"Suggested learning path:\n{path_str}\n\n"
            "Call report_recommendation with summary, learning_path, and tips."
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
