"""
api/schemas.py

Pydantic request / response models for the FastAPI /recommend endpoint.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Request
# ─────────────────────────────────────────────────────────────────────────────

class FiltersModel(BaseModel):
    """Optional metadata filters to narrow course retrieval."""
    difficulty:   Optional[str]   = Field(None, example="Beginner")
    min_rating:   Optional[float] = Field(None, example=4.5)
    organization: Optional[str]   = Field(None, example="DeepLearning.AI")
    course_type:  Optional[str]   = Field(None, example="Course")


class RecommendRequest(BaseModel):
    """Incoming student recommendation request."""
    query:   str            = Field(..., min_length=3, example="I want to learn machine learning as a beginner")
    filters: Optional[FiltersModel] = Field(None)


# ─────────────────────────────────────────────────────────────────────────────
# Response building blocks
# ─────────────────────────────────────────────────────────────────────────────

class IntentSchema(BaseModel):
    topic:        str
    level:        str
    career_goal:  str
    known_skills: list[str]
    keywords:     list[str]
    search_query: str


class CourseSchema(BaseModel):
    course_id:    Optional[str]   = None
    course_name:  Optional[str]   = None
    organization: Optional[str]   = None
    difficulty:   Optional[str]   = None
    rating:       Optional[float] = None
    skills:       Optional[str]   = None
    course_url:   Optional[str]   = None


class SkillGapSchema(BaseModel):
    has_gaps:            bool
    missing_skills:      list[str]
    foundational_topics: list[str]


class LearningPathStageSchema(BaseModel):
    stage:   str
    courses: list[CourseSchema]


class CareerAlignmentSchema(BaseModel):
    career_track:     str
    top_course_ids:   list[str]
    alignment_reason: str


class RecommendationSchema(BaseModel):
    summary:       str
    learning_path: list[str]
    tips:          list[str]


# ─────────────────────────────────────────────────────────────────────────────
# Full response
# ─────────────────────────────────────────────────────────────────────────────

class RecommendResponse(BaseModel):
    """Full recommendation response returned by /recommend."""
    intent:           IntentSchema
    courses:          list[CourseSchema]
    skill_gap:        SkillGapSchema
    learning_path:    list[LearningPathStageSchema]
    career_alignment: CareerAlignmentSchema
    recommendation:   RecommendationSchema
    message:          str = "Recommendations generated successfully."
