"""
app_agents/skill_gap_agent.py

SkillGapAgent — identifies missing prerequisite skills given the
retrieved courses and the student's stated experience level.

Single-tool pipeline:
  report_skill_gap — output gaps + foundational topics to search
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
from app_agents.tools import report_skill_gap
from api.utils.token_utils import count_tokens

log = get_logger("skill_gap_agent")


# ─────────────────────────────────────────────────────────────────────────────
# Output schema
# ─────────────────────────────────────────────────────────────────────────────

class SkillGapResult(BaseModel):
    has_gaps:            bool
    missing_skills:      list[str]
    foundational_topics: list[str]   # used to search for bridging courses
    usage:               dict = {}   # {input, output, model}


# ─────────────────────────────────────────────────────────────────────────────
# Agent definition
# ─────────────────────────────────────────────────────────────────────────────

skill_gap_agent = Agent(
    name="SkillGapAgent",
    model=LLM_MODEL,
    instructions="""
You are an academic prerequisite analyst for a university course discovery system.

You will receive:
  - The student's level  (Beginner / Intermediate / Advanced / Any)
  - Skills the student ALREADY knows
  - A numbered list of recommended courses with their required skills

Your job is to call report_skill_gap EXACTLY ONCE with your analysis.

─── Analysis Rules ──────────────────────────────────────────────
- Beginner students: flag gaps if courses require programming,
  mathematics, or domain knowledge beyond high-school level.
- Intermediate students: flag gaps only if courses require
  specialised prerequisites not commonly known.
- Advanced students: assume strong background — flag gaps only for
  highly specific prerequisites.
- If level is "Any": be conservative, flag obvious gaps only.
- DO NOT flag a skill as missing if it is in the student's known skills list or is a close synonym of a known skill.

- missing_skills: concrete skills/knowledge areas the student likely
  lacks (e.g. "Python programming", "calculus", "SQL").
- foundational_topics: short search phrases to find bridging courses
  (e.g. "Python for beginners", "intro to linear algebra").
  Keep each phrase under 6 words.
- If no meaningful gaps exist, set has_gaps=false and both lists empty.
─────────────────────────────────────────────────────────────────
Always call report_skill_gap. Never respond in plain text.
""",
    tools=[report_skill_gap],
)

log.info("[Agent:created] SkillGapAgent | model=%s", LLM_MODEL)


# ─────────────────────────────────────────────────────────────────────────────
# Class wrapper
# ─────────────────────────────────────────────────────────────────────────────

class SkillGapAgent:
    """
    Usage:
        agent = SkillGapAgent()
        result: SkillGapResult = await agent.analyse(level, courses)
    """

    def __init__(self) -> None:
        log.debug("[SkillGapAgent] initialised")

    async def analyse(self, level: str, known_skills: list[str], courses: list[dict]) -> SkillGapResult:
        log.info("[SkillGapAgent:analyse] START | level=%r | known=%s | courses=%d", level, known_skills, len(courses))

        prompt = self._build_prompt(level, known_skills, courses)

        t0 = time.perf_counter()
        result = await Runner.run(skill_gap_agent, prompt)
        elapsed = time.perf_counter() - t0

        log.info("[SkillGapAgent:analyse] finished | elapsed=%.2fs", elapsed)

        gap = self._extract_result(result)

        # Estimate tokens
        input_tokens  = count_tokens(prompt, LLM_MODEL)
        output_tokens = count_tokens(result.final_output or str(gap.model_dump()), LLM_MODEL)
        gap.usage = {"agent": "SkillGapAgent", "input": input_tokens, "output": output_tokens, "model": LLM_MODEL}

        log.info(
            "[SkillGapAgent:analyse] END | has_gaps=%s | missing=%s | tokens=%d",
            gap.has_gaps, gap.missing_skills, input_tokens + output_tokens
        )
        return gap

    def _build_prompt(self, level: str, known_skills: list[str], courses: list[dict]) -> str:
        lines = [
            f"Student level: {level}",
            f"Student already knows: {', '.join(known_skills) if known_skills else 'None stated'}\n",
            "Recommended courses:"
        ]
        for i, c in enumerate(courses, 1):
            lines.append(
                f"  {i}. {c.get('course_name')} ({c.get('difficulty')}) — "
                f"Skills: {(c.get('skills') or '')[:80]}"
            )
        lines.append("\nCall report_skill_gap with your analysis.")
        return "\n".join(lines)

    def _extract_result(self, result) -> SkillGapResult:
        for item in result.new_items:
            if type(item).__name__ == "ToolCallOutputItem":
                parsed = self._safe_json(getattr(item, "output", ""))
                if parsed and "has_gaps" in parsed:
                    return SkillGapResult(**parsed)

        log.warning("[SkillGapAgent] tool not called — returning no-gap fallback")
        return SkillGapResult(has_gaps=False, missing_skills=[], foundational_topics=[])

    def _safe_json(self, raw) -> dict | None:
        try:
            return json.loads(str(raw))
        except Exception:
            return None
