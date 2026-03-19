"""
Source/api/utils/token_utils.py

Utility for calculating token usage and estimating cost for OpenAI models.
Supports tiktoken for precise counting and logs to a separate file.
"""

import tiktoken
import os
import json
from datetime import datetime
from logger import get_logger

# Register a specialized logger for token usage
# This will create logs/token_usage.log via the get_logger helper
token_log = get_logger("token_usage")

# Pricing per 1M tokens (USD) - As of March 2024 for GPT-4o
PRICING = {
    "gpt-4o": {
        "input": 5.00,
        "output": 15.00
    },
    "text-embedding-3-small": {
        "input": 0.02,
        "output": 0.00
    }
}

def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Counts the number of tokens in a string using tiktoken.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to rough estimation (4 chars per token) if tiktoken fails
        return len(text) // 4

def calculate_cost(input_tokens: int, output_tokens: int, model: str = "gpt-4o") -> float:
    """
    Calculates the estimated cost in USD based on token counts and model pricing.
    """
    prices = PRICING.get(model, PRICING["gpt-4o"])
    
    input_cost = (input_tokens / 1_000_000) * prices["input"]
    output_cost = (output_tokens / 1_000_000) * prices["output"]
    
    return input_cost + output_cost

def log_token_run(
    query: str,
    agents_usage: list[dict], # list of {"agent": str, "input": int, "output": int, "model": str}
    total_duration: float
):
    """
    Aggregates usage across all agents in a single run and logs to token_usage.log.
    """
    total_input = 0
    total_output = 0
    total_cost = 0.0
    
    details = []
    
    for usage in agents_usage:
        agent_name = usage.get("agent", "Unknown")
        model = usage.get("model", "gpt-4o")
        i_tokens = usage.get("input", 0)
        o_tokens = usage.get("output", 0)
        
        cost = calculate_cost(i_tokens, o_tokens, model)
        
        total_input += i_tokens
        total_output += o_tokens
        total_cost += cost
        
        details.append({
            "agent": agent_name,
            "model": model,
            "input": i_tokens,
            "output": o_tokens,
            "cost_usd": round(cost, 6)
        })

    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": query[:50] + "..." if len(query) > 50 else query,
        "total_input": total_input,
        "total_output": total_output,
        "total_tokens": total_input + total_output,
        "total_cost_usd": round(total_cost, 6),
        "duration_s": round(total_duration, 2),
        "agent_details": details
    }
    
    # Log as formatted JSON for easy parsing later
    token_log.info(f"RUN_SUMMARY: {json.dumps(log_entry)}")
