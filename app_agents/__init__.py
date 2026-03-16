"""
app_agents/__init__.py

Load environment variables FIRST so the openai-agents SDK trace exporter
can read OPENAI_API_KEY from .env at import time.
"""
import os
import sys

from dotenv import load_dotenv
load_dotenv()                   # must run before 'from agents import ...'

from agents import Agent, Runner, function_tool   # noqa: F401  (re-exported for submodules)