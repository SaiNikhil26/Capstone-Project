"""
app_agents/sequencer.py

CourseSequencer — orders retrieved courses into a structured
learning path using rule-based difficulty sorting.

No LLM required — pure logic.

Difficulty order: Beginner → Intermediate → Advanced → Mixed → Unknown
"""

from __future__ import annotations

import sys
import os
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import get_logger

log = get_logger("sequencer")

# ─────────────────────────────────────────────────────────────────────────────
# Difficulty sort order
# ─────────────────────────────────────────────────────────────────────────────

_DIFFICULTY_ORDER: dict[str, int] = {
    "beginner":     0,
    "intermediate": 1,
    "advanced":     2,
    "mixed":        3,
}

_STAGE_LABELS: dict[int, str] = {
    0: "Stage 1 — Foundations",
    1: "Stage 2 — Core Skills",
    2: "Stage 3 — Advanced Topics",
    3: "Stage 4 — Specialisation",
}


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
# Sequencer
# ─────────────────────────────────────────────────────────────────────────────

class CourseSequencer:
    """
    Usage:
        seq = CourseSequencer()
        path: LearningPath = seq.sequence(courses)
    """

    def __init__(self) -> None:
        log.debug("[CourseSequencer] initialised")

    def sequence(self, courses: list[dict]) -> LearningPath:
        """
        Sort courses by difficulty and group into named stages.

        Args:
            courses: List of slim course dicts (must have 'difficulty' key).

        Returns:
            LearningPath with stages and a flat ordered name list.
        """
        log.info("[CourseSequencer:sequence] START | courses=%d", len(courses))

        # Sort by difficulty rank, then by rating descending within same level
        def _sort_key(c: dict):
            diff = (c.get("difficulty") or "").lower()
            rank = _DIFFICULTY_ORDER.get(diff, 4)
            rating = float(c.get("rating") or 0)
            return (rank, -rating)

        sorted_courses = sorted(courses, key=_sort_key)

        # Group into stages
        stage_buckets: dict[int, list[dict]] = {}
        for c in sorted_courses:
            diff = (c.get("difficulty") or "").lower()
            rank = _DIFFICULTY_ORDER.get(diff, 4)
            stage_buckets.setdefault(rank, []).append(c)

        stages: list[LearningPathStage] = []
        for rank in sorted(stage_buckets):
            label = _STAGE_LABELS.get(rank, f"Stage {rank + 1}")
            stages.append(LearningPathStage(
                stage=label,
                courses=stage_buckets[rank],
            ))

        ordered_names = [
            c.get("course_name", "Unknown")
            for stage in stages
            for c in stage.courses
        ]

        log.info(
            "[CourseSequencer:sequence] END | stages=%d | total=%d",
            len(stages), len(ordered_names),
        )
        return LearningPath(stages=stages, ordered_names=ordered_names)
