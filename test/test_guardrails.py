"""
test_guardrails.py

A simple script to test the GuardrailValidator with PII.
"""

import sys
import asyncio

sys.path.append(".")
from guardrails.validator import GuardrailValidator

async def main():
    validator = GuardrailValidator()
    
    test_queries = [
        "I want to learn machine learning.",
        "Hi, my name is John Doe and my email is john.doe@example.com. I want to learn data science.",
        "Call me at 555-123-4567 to sign me up for a biology class."
    ]
    
    print("Testing GuardrailValidator with Presidio PII Redaction...\n")
    for q in test_queries:
        print(f"Original: {q}")
        try:
            redacted = await validator.validate(q)
            print(f"Redacted: {redacted}")
        except Exception as e:
            print(f"Rejected: {e}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
