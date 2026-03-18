"""
app_agents/sequencer.py

CourseSequencer — orders retrieved courses into a structured
learning path using LLM-based reasoning.

Orders courses by conceptual dependency and creates themed milestones.
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
from app_agents.tools import report_learning_sequence

log = get_logger("sequencer")


# ─────────────────────────────────────────────────────────────────────────────
# Output schema
# ─────────────────────────────────────────────────────────────────────────────

class LearningPathStage(BaseModel):
    stage:   str
    courses: list[dict]


class LearningPath(BaseModel):
    stages:        list[LearningPathStage]
    ordered_names: list[str]   # flat ordered list of course names


# ─────────────────────────────────────────────────────────────────────────────
# Agent definition
# ─────────────────────────────────────────────────────────────────────────────

sequencer_agent = Agent(
    name="SequencerAgent",
    model=LLM_MODEL,
    instructions="""
You are an academic curriculum designer. Your job is to take a list of 10 courses and organize them into a logical, multi-stage learning path.

You will receive:
  - The student's career goal.
  - A list of recommended courses with their IDs, difficulties, and skills.

─── Rules ───────────────────────────────────────────────────────
1.  **Logical Flow**: Order courses by conceptual dependency (e.g., learn Python before learn Data Science with Python).
2.  **Themed Stages**: Group courses into 2-4 stages. 
3.  **Creative Naming**: Instead of "Stage 1", use themed names like "Foundational Tools", "Core Machine Learning", or "Advanced Specialisation".
4.  **Final Top 5**: Focus the sequence on the most relevant 3-5 courses, but maintain the logical order for all 10 if they are distinct.
5.  **Output**: Always call report_learning_sequence EXACTLY ONCE.

─── Metadata Sensitivity ────────────────────────────────────────
Use the 'difficulty' and 'skills' fields to inform your ordering. Even if two courses are 'Beginner', one might naturally come before another.
─────────────────────────────────────────────────────────────────
Always call report_learning_sequence. Never respond in plain text.
""",
    tools=[report_learning_sequence],
)

log.info("[Agent:created] SequencerAgent | model=%s", LLM_MODEL)


# ─────────────────────────────────────────────────────────────────────────────
# Class wrapper
# ─────────────────────────────────────────────────────────────────────────────

class CourseSequencer:
    """
    Usage:
        seq = CourseSequencer()
        path: LearningPath = await seq.sequence(career_goal, courses)
    """

    def __init__(self) -> None:
        log.debug("[CourseSequencer] initialised (Agentic)")

    async def sequence(self, career_goal: str, courses: list[dict]) -> LearningPath:
        log.info("[CourseSequencer:sequence] START | goal=%r | courses=%d", career_goal, len(courses))

        prompt = self._build_prompt(career_goal, courses)

        t0 = time.perf_counter()
        result = await Runner.run(sequencer_agent, prompt)
        elapsed = time.perf_counter() - t0

        log.info("[CourseSequencer:sequence] finished | elapsed=%.2fs", elapsed)

        path_data = self._extract_result(result, courses)
        return path_data

    def _build_prompt(self, goal: str, courses: list[dict]) -> str:
        lines = [f"Student goal: {goal}\n", "Courses to sequence:"]
        for i, c in enumerate(courses, 1):
            lines.append(
                f"  - [{c.get('course_id')}] {c.get('course_name')} "
                f"({c.get('difficulty')}) — Skills: {c.get('skills')} - Description: {c.get('description')}"
            )
        lines.append("\nCall report_learning_sequence with your path design.")
        return "\n".join(lines)

    def _extract_result(self, result, original_courses: list[dict]) -> LearningPath:
        # Build ID lookup
        course_map = {c.get("course_id"): c for c in original_courses}
        
        for item in result.new_items:
            if type(item).__name__ == "ToolCallOutputItem":
                parsed = self._safe_json(getattr(item, "output", ""))
                if parsed and "stages" in parsed:
                    stages = []
                    ordered_names = []
                    
                    for s in parsed["stages"]:
                        stage_name = s.get("stage", "Untitled Stage")
                        ids = s.get("course_ids", [])
                        
                        # Map IDs back to full course dicts
                        stage_courses = [course_map[cid] for cid in ids if cid in course_map]
                        
                        if stage_courses:
                            stages.append(LearningPathStage(
                                stage=stage_name,
                                courses=stage_courses
                            ))
                            ordered_names.extend([c.get("course_name") for c in stage_courses])
                    
                    return LearningPath(stages=stages, ordered_names=ordered_names)

        log.warning("[CourseSequencer] tool not called — returning empty fallback")
        return LearningPath(stages=[], ordered_names=[])

    def _safe_json(self, raw) -> dict | None:
        try:
            return json.loads(str(raw))
        except Exception:
            return None
