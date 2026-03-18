"""
agents/intent_agent.py

IntentAgent — understands a raw student query and retrieves matching courses.

Two-tool pipeline (both called by the agent in sequence):

  Step 1 → extract_intent   (agents/tools.py)
           Parse topic, level, career_goal, keywords, search_query from the query.

  Step 2 → search_courses   (agents/tools.py)
           Build the hybrid_search payload from the extracted intent and
           retrieve the top matching courses from the vector + keyword index.

Agent pattern mirrors Day_29/genai_ecommerce_assistant:
  - openai-agents SDK  (Agent + @function_tool + Runner)
  - Class wrapper (IntentAgent) with a clean async interface for callers
  - All tool logic lives in agents/tools.py
  - Structured logger calls at every decision point
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
from app_agents.tools import extract_intent, search_courses

log = get_logger("intent_agent")


# ─────────────────────────────────────────────────────────────────────────────
# Output schemas
# ─────────────────────────────────────────────────────────────────────────────

class ParsedIntent(BaseModel):
    """Structured learning intent extracted from the student's raw query."""
    topic:        str        # Main subject area   e.g. "machine learning"
    level:        str        # Difficulty hint     e.g. "Beginner" | "Intermediate" | "Advanced" | "Any"
    career_goal:  str        # Career aspiration   e.g. "data scientist" | "not specified"
    known_skills: list[str]  # Skills the student already knows
    keywords:     list[str]  # Key terms to sharpen retrieval
    search_query: str        # Optimised query string passed to hybrid_search


class IntentResult(BaseModel):
    """Combined output returned by IntentAgent.parse()."""
    intent:  ParsedIntent
    courses: list[dict]      # Slimmed course records from hybrid_search


# ─────────────────────────────────────────────────────────────────────────────
# Agent definition
# ─────────────────────────────────────────────────────────────────────────────

intent_agent = Agent(
    name="IntentAgent",
    model=LLM_MODEL,
    instructions="""
You are an academic intent parser and course retrieval agent for a university
course discovery system.

Your job is a strict TWO-STEP process:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — Call extract_intent (EXACTLY ONCE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Analyse the student's query and extract:

  topic         Main academic/technical subject (noun phrase, not a sentence)
                e.g. "machine learning", "financial markets"

  level         Difficulty signal:
                  Beginner     → "beginner", "new to", "introduction", "basics"
                  Intermediate → "some experience", "already know basics"
                  Advanced     → "advanced", "expert", "deep dive"
                  Any          → no clear signal (default)

  career_goal   Role the student mentions: "data scientist", "AI engineer".
                Use "not specified" if absent.

  known_skills  Technical skills the student explicitly says they ALREADY know.
                Ensure you capture ALL of these. e.g. ["Python", "statistics"].
                Use [] if none mentioned.

  keywords      3-6 specific technical terms that sharpen retrieval.

  search_query  One compact string (max 15 words) for the retriever.
                Combine topic + keywords. Write for a search engine, not prose.
                Example: "machine learning algorithms Python data science beginners"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — Call search_courses (EXACTLY ONCE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use the values from STEP 1 to build the search payload:

  query         ← use search_query from STEP 1
  difficulty    ← map level: Beginner→"Beginner", Intermediate→"Intermediate",
                             Advanced→"Advanced". OMIT if level is "Any".
  min_rating    ← only set if student mentioned a quality/rating requirement.
  organization  ← only set if student named a specific provider.
  course_type   ← only set if student specified a course format.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- ALWAYS call BOTH tools — never respond in plain text.
- Call extract_intent FIRST, search_courses SECOND.
- Call each tool EXACTLY ONCE.
- Never fabricate information not present in the query.
- Do NOT add filters the student did not explicitly request.
""",
    tools=[extract_intent, search_courses],
)

log.info(
    "[Agent:created] IntentAgent | model=%s | tools=[extract_intent, search_courses]",
    LLM_MODEL,
)


# ─────────────────────────────────────────────────────────────────────────────
# Class wrapper  (mirrors OrchestratorAgent style from Day_29 project)
# ─────────────────────────────────────────────────────────────────────────────

class IntentAgent:
    """
    Thin class wrapper around the openai-agents IntentAgent.

    Usage:
        agent = IntentAgent()
        result: IntentResult = await agent.parse(query)
        # result.intent  → ParsedIntent
        # result.courses → list[dict]  slimmed course records
    """

    def __init__(self) -> None:
        log.debug("[IntentAgent] initialised")

    # ── Public API ────────────────────────────────────────────────────────────

    async def parse(self, query: str, filters: dict | None = None) -> IntentResult:
        """
        Parse a raw student query into structured intent and retrieve
        the top matching courses from the catalog.

        Args:
            query: The student's natural-language learning query.
            filters: Explicit UI filters passed from the frontend.

        Returns:
            IntentResult containing parsed intent and matched courses.
        """
        log.info("[IntentAgent:parse] START | query=%r | filters=%r", query, filters)

        prompt = self._build_prompt(query, filters)

        t0 = time.perf_counter()
        result = await Runner.run(intent_agent, prompt)
        elapsed = time.perf_counter() - t0

        log.info("[IntentAgent:parse] agent finished | elapsed=%.2fs", elapsed)

        intent, courses = self._extract_results(result)

        log.info(
            "[IntentAgent:parse] END | topic=%r | level=%r | courses=%d",
            intent.topic, intent.level, len(courses),
        )

        return IntentResult(intent=intent, courses=courses)

    # ── Prompt builder ────────────────────────────────────────────────────────

    def _build_prompt(self, query: str, filters: dict | None = None) -> str:
        base_prompt = f"Student query: {query}\n\n"
        
        if filters:
            base_prompt += (
                f"EXPLICIT USER FILTERS (MUST be passed EXACTLY as provided to search_courses):\n"
                f"{json.dumps(filters)}\n\n"
            )

        base_prompt += (
            "Follow the two-step process:\n"
            "1. Call extract_intent with the structured intent.\n"
            "2. Call search_courses using the extracted search_query and any explicit user filters provided above."
        )
        return base_prompt

    # ── Result extractor ──────────────────────────────────────────────────────

    def _extract_results(self, result) -> tuple[ParsedIntent, list[dict]]:
        """
        Walk Runner result items to collect outputs from both tools.
        Returns (ParsedIntent, list[course_dicts]).
        """
        intent_data: dict | None = None
        courses: list[dict] = []

        for item in result.new_items:
            item_type = type(item).__name__

            if item_type == "ToolCallItem":
                raw_item = getattr(item, "raw_item", None)
                tool_name = getattr(raw_item, "name", "unknown")
                log.info("[IntentAgent:_extract_results] tool called: %s", tool_name)

            elif item_type == "ToolCallOutputItem":
                raw_output = getattr(item, "output", "")
                log.debug("[IntentAgent:_extract_results] tool output: %s", raw_output[:200])

                parsed = self._safe_json(raw_output)
                if not parsed:
                    continue

                # extract_intent output → has "topic" key
                if "topic" in parsed:
                    intent_data = parsed
                    log.debug("[IntentAgent:_extract_results] captured intent")

                # search_courses output → has "courses" key
                elif "courses" in parsed:
                    courses = parsed.get("courses", [])
                    log.info(
                        "[IntentAgent:_extract_results] captured %d courses",
                        len(courses),
                    )

        # Build ParsedIntent (fallback if tool was skipped)
        if intent_data and "topic" in intent_data:
            intent = ParsedIntent(**{
                k: intent_data[k]
                for k in ParsedIntent.model_fields
                if k in intent_data
            })
        else:
            log.warning(
                "[IntentAgent:_extract_results] extract_intent not called — using fallback"
            )
            intent = ParsedIntent(
                topic="general",
                level="Any",
                career_goal="not specified",
                known_skills=[],
                keywords=[],
                search_query=result.final_output or "general courses",
            )

        return intent, courses

    # ── Safe JSON parser ──────────────────────────────────────────────────────

    def _safe_json(self, raw) -> dict | None:
        try:
            return json.loads(str(raw))
        except Exception:
            return None
