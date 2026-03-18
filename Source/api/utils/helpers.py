"""
api/utils/helpers.py

Utility functions for validation and data formatting.
"""

from fastapi import HTTPException
from typing import Set

from api.schemas import CourseSchema

_MIN_QUERY_LEN = 3
_LEARNING_KEYWORDS: Set[str] = {
    "learn", "study", "understand", "become", "explore", "know",
    "teach", "course", "skill", "career", "want", "need", "how",
    "start", "improve", "beginner", "advanced", "intermediate",
}

def validate_query(query: str) -> None:
    """Raise HTTPException 422 if the query fails guardrails."""
    q = query.strip()
    if len(q) < _MIN_QUERY_LEN:
        raise HTTPException(
            status_code=422,
            detail=f"Query too short (min {_MIN_QUERY_LEN} characters).",
        )
    words = set(q.lower().split())
    if not words.intersection(_LEARNING_KEYWORDS):
        raise HTTPException(
            status_code=422,
            detail=(
                "Query does not appear to be a learning-related request. "
                "Please describe what you want to learn or a career goal."
            ),
        )

def to_course_schema(c: dict) -> CourseSchema:
    return CourseSchema(
        course_id=c.get("course_id"),
        course_name=c.get("course_name"),
        organization=c.get("organization"),
        difficulty=c.get("difficulty"),
        rating=c.get("rating"),
        skills=c.get("skills"),
        course_url=c.get("course_url"),
    )
