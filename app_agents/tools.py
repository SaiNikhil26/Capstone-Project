"""
agents/tools.py

All @function_tool definitions used by the agent network.
Each tool wraps a backend service (hybrid retriever, etc.) and
returns a JSON string so the agent can reason over results.

Tools defined here:
    extract_intent   — parse learning intent from a student query
    search_courses   — build hybrid_search payload and retrieve courses
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from agents import function_tool

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import get_logger
from retrieval.hybrid_retriever import hybrid_search

log = get_logger("agent_tools")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

# Compact per-course view returned to the agent (keeps token usage low)
_SLIM_FIELDS = [
    "course_id", "course_name", "organization",
    "difficulty", "rating", "skills", "course_url",
]

def _slim_course(course: dict) -> dict:
    """Keep only the fields agents need — drops heavy payload / page_content."""
    slim = {k: course.get(k) for k in _SLIM_FIELDS}
    if slim.get("skills"):
        slim["skills"] = slim["skills"][:100]   # truncate to reduce tokens
    return slim


# Map level strings the agent produces → Qdrant difficulty values
_LEVEL_TO_DIFFICULTY: dict[str, str] = {
    "beginner":     "Beginner",
    "intermediate": "Intermediate",
    "advanced":     "Advanced",
    "mixed":        "Mixed",
}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — extract_intent
# ─────────────────────────────────────────────────────────────────────────────

@function_tool
def extract_intent(
    topic:        str,
    level:        str,
    career_goal:  str,
    keywords:     list[str],
    search_query: str,
) -> str:
    """
    Record the structured learning intent extracted from the student query.
    Call this tool FIRST, EXACTLY ONCE, before calling search_courses.

    Args:
        topic:        Main subject the student wants to learn
                      (e.g. "machine learning"). Use a noun phrase, not a sentence.
        level:        Difficulty hint — must be one of:
                      "Beginner", "Intermediate", "Advanced", or "Any".
        career_goal:  Career path or role the student aspires to
                      (e.g. "data scientist"). Use "not specified" if unclear.
        keywords:     3-6 specific technical or domain keywords that
                      sharpen retrieval accuracy.
        search_query: A concise search string (max 15 words) combining
                      topic + keywords for the hybrid retriever.
                      Write for a search engine, not prose.
    """
    log.info(
        "[extract_intent] topic=%r | level=%r | career_goal=%r | keywords=%s",
        topic, level, career_goal, keywords,
    )

    intent = {
        "topic":        topic,
        "level":        level,
        "career_goal":  career_goal,
        "keywords":     keywords,
        "search_query": search_query,
    }
    return json.dumps(intent)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — search_courses
# ─────────────────────────────────────────────────────────────────────────────

@function_tool
def search_courses(
    query:        str,
    difficulty:   Optional[str]   = None,
    min_rating:   Optional[float] = None,
    organization: Optional[str]   = None,
    course_type:  Optional[str]   = None,
) -> str:
    """
    Search the course catalog using the hybrid retriever (semantic + keyword).
    Call this tool SECOND, after extract_intent, using the search_query
    and any filters derived from the extracted intent.

    Args:
        query:        The search_query string produced by extract_intent.
        difficulty:   Optional difficulty filter. Must exactly match one of:
                      "Beginner", "Intermediate", "Advanced", "Mixed".
                      Only set this when the student explicitly stated a level.
                      OMIT (leave None) when level is "Any".
        min_rating:   Optional minimum course rating (0.0 – 5.0).
                      Only set if the student requested a quality threshold.
        organization: Optional provider filter (e.g. "DeepLearning.AI", "Google").
                      Only set if the student explicitly named a provider.
        course_type:  Optional course-format filter (e.g. "Course", "Specialization").
                      Only set if explicitly mentioned by the student.
    """
    log.info(
        "[search_courses] query=%r | difficulty=%r | min_rating=%s | "
        "organization=%r | course_type=%r",
        query, difficulty, min_rating, organization, course_type,
    )

    # Build filters dict — only include keys that were actually specified
    filters: dict = {}
    if difficulty and difficulty.lower() != "any":
        filters["difficulty"] = _LEVEL_TO_DIFFICULTY.get(
            difficulty.lower(), difficulty
        )
    if min_rating is not None:
        filters["min_rating"] = float(min_rating)
    if organization:
        filters["organization"] = organization
    if course_type:
        filters["course_type"] = course_type

    log.debug("[search_courses] resolved filters: %s", filters)

    try:
        # hybrid_search(query: str, filters: dict = None) → list[dict]
        courses = hybrid_search(
            query=query,
            filters=filters if filters else None,
        )
        log.info("[search_courses] hybrid_search returned %d courses", len(courses))
    except Exception as exc:
        log.error("[search_courses] hybrid_search failed: %s", exc)
        return json.dumps({"error": str(exc), "courses": []})

    slim_courses = [_slim_course(c) for c in courses]
    log.info("[search_courses] returning %d slimmed courses", len(slim_courses))
    return json.dumps({"count": len(slim_courses), "courses": slim_courses})




# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 — report_skill_gap
# ─────────────────────────────────────────────────────────────────────────────

@function_tool
def report_skill_gap(
    has_gaps:            bool,
    missing_skills:      list[str],
    foundational_topics: list[str],
) -> str:
    """
    Record the skill gap analysis result. Call this tool EXACTLY ONCE
    after analysing the courses and student level.

    Args:
        has_gaps:            True if the student is likely missing prerequisite skills.
        missing_skills:      List of specific skills the student likely lacks
                             (e.g. ["Linear Algebra", "Python basics"]).
                             Empty list if no gaps found.
        foundational_topics: Search topics to find bridging/foundational courses
                             (e.g. ["Python for beginners", "statistics fundamentals"]).
                             Empty list if no gaps found.
    """
    log.info(
        "[report_skill_gap] has_gaps=%s | missing=%s | topics=%s",
        has_gaps, missing_skills, foundational_topics,
    )
    return json.dumps({
        "has_gaps":            has_gaps,
        "missing_skills":      missing_skills,
        "foundational_topics": foundational_topics,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4 — report_career_alignment
# ─────────────────────────────────────────────────────────────────────────────

@function_tool
def report_career_alignment(
    career_track:       str,
    top_course_ids:     list[str],
    alignment_reason:   str,
) -> str:
    """
    Record the career alignment result. Call this tool EXACTLY ONCE
    after mapping the courses to the student's career goal.

    Args:
        career_track:     The identified career track
                          (e.g. "Data Scientist", "AI Engineer", "General").
        top_course_ids:   Ordered list of course_ids most relevant to the career
                          (from the provided course list, pick the best 3-5).
        alignment_reason: One short sentence explaining why these courses
                          fit the career track.
    """
    log.info(
        "[report_career_alignment] track=%r | top_ids=%s",
        career_track, top_course_ids,
    )
    return json.dumps({
        "career_track":     career_track,
        "top_course_ids":   top_course_ids,
        "alignment_reason": alignment_reason,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool 5 — report_recommendation
# ─────────────────────────────────────────────────────────────────────────────

@function_tool
def report_recommendation(
    summary:       str,
    learning_path: list[str],
    tips:          list[str],
) -> str:
    """
    Record the final learning recommendation. Call this tool EXACTLY ONCE
    after reviewing all inputs (intent, courses, skill gaps, career alignment).

    Args:
        summary:       2-3 sentence advisory message for the student explaining
                       the recommendations and any important considerations.
        learning_path: Ordered list of course names forming the suggested
                       learning path (3-5 courses, easiest first).
        tips:          2-3 short, actionable study tips tailored to the student's
                       goal and current level.
    """
    log.info("[report_recommendation] path_length=%d", len(learning_path))
    return json.dumps({
        "summary":       summary,
        "learning_path": learning_path,
        "tips":          tips,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Registry log
# ─────────────────────────────────────────────────────────────────────────────

log.info(
    "[tools] defined: %s",
    [
        extract_intent.name,
        search_courses.name,
        report_skill_gap.name,
        report_career_alignment.name,
        report_recommendation.name,
    ],
)
