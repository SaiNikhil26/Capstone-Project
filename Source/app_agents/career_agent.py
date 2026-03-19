"""
app_agents/career_agent.py

CareerAgent — maps retrieved courses to the student's career track
and highlights the most career-relevant ones.

Single-tool pipeline:
  report_career_alignment — output career track + top course IDs
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
from app_agents.tools import report_career_alignment
from api.utils.token_utils import count_tokens

log = get_logger("career_agent")


# ─────────────────────────────────────────────────────────────────────────────
# Output schema
# ─────────────────────────────────────────────────────────────────────────────

class CareerAlignmentResult(BaseModel):
    career_track:     str
    top_course_ids:   list[str]
    alignment_reason: str
    usage:            dict = {}   # {input, output, model}


# ─────────────────────────────────────────────────────────────────────────────
# Agent definition
# ─────────────────────────────────────────────────────────────────────────────

career_agent = Agent(
    name="CareerAgent",
    model=LLM_MODEL,
    instructions="""
You are a career-oriented course advisor for a university course discovery system.

You will receive:
  - The student's career goal (e.g. "data scientist", "AI engineer", "not specified")
  - A numbered list of courses with their IDs, difficulty, and skills

Your job is to call report_career_alignment EXACTLY ONCE.

─── Rules ───────────────────────────────────────────────────────
- Identify the most appropriate career_track from the goal.
  If no goal is stated, use "General Tech Skills".
- Pick the 3-5 course_ids (from the provided list) most useful
  for that career track. Prioritise practical, skill-building courses.
- Write a single concise sentence for alignment_reason explaining the fit.
─────────────────────────────────────────────────────────────────
Always call report_career_alignment. Never respond in plain text.
""",
    tools=[report_career_alignment],
)

log.info("[Agent:created] CareerAgent | model=%s", LLM_MODEL)


# ─────────────────────────────────────────────────────────────────────────────
# Class wrapper
# ─────────────────────────────────────────────────────────────────────────────

class CareerAgent:
    """
    Usage:
        agent = CareerAgent()
        result: CareerAlignmentResult = await agent.align(career_goal, courses)
    """

    def __init__(self) -> None:
        log.debug("[CareerAgent] initialised")

    async def align(self, career_goal: str, courses: list[dict]) -> CareerAlignmentResult:
        log.info("[CareerAgent:align] START | goal=%r | courses=%d", career_goal, len(courses))

        prompt = self._build_prompt(career_goal, courses)

        t0 = time.perf_counter()
        result = await Runner.run(career_agent, prompt)
        elapsed = time.perf_counter() - t0

        log.info("[CareerAgent:align] finished | elapsed=%.2fs", elapsed)

        alignment = self._extract_result(result)

        # Estimate tokens
        input_tokens  = count_tokens(prompt, LLM_MODEL)
        output_tokens = count_tokens(result.final_output or str(alignment.model_dump()), LLM_MODEL)
        alignment.usage = {"agent": "CareerAgent", "input": input_tokens, "output": output_tokens, "model": LLM_MODEL}

        log.info(
            "[CareerAgent:align] END | track=%r | top=%s | tokens=%d",
            alignment.career_track, alignment.top_course_ids, input_tokens + output_tokens
        )
        return alignment

    def _build_prompt(self, career_goal: str, courses: list[dict]) -> str:
        lines = [f"Student career goal: {career_goal}\n", "Available courses:"]
        for i, c in enumerate(courses, 1):
            lines.append(
                f"  {i}. [{c.get('course_id', '?')}] {c.get('course_name')} "
                f"({c.get('difficulty')}) — Skills: {(c.get('skills') or '')[:80]}"
            )
        lines.append("\nCall report_career_alignment with your analysis.")
        return "\n".join(lines)

    def _extract_result(self, result) -> CareerAlignmentResult:
        for item in result.new_items:
            if type(item).__name__ == "ToolCallOutputItem":
                parsed = self._safe_json(getattr(item, "output", ""))
                if parsed and "career_track" in parsed:
                    return CareerAlignmentResult(**parsed)

        log.warning("[CareerAgent] tool not called — returning fallback")
        return CareerAlignmentResult(
            career_track="General",
            top_course_ids=[],
            alignment_reason="No specific career alignment identified.",
        )

    def _safe_json(self, raw) -> dict | None:
        try:
            return json.loads(str(raw))
        except Exception:
            return None
