"""Run the demo inputs through build_plan and save the results to demo_cache.json.

Usage (from backend/, venv active):  python build_demo_cache.py

main.py returns these saved responses when a /plan request's situation text exactly
matches one of these inputs (leading/trailing whitespace ignored), so a rate limit or
outage can't break the live demo. Paste these exact strings during the demo.
"""

import json
import sys
from pathlib import Path

from agent import build_plan

DEMO_INPUTS = [
    "I'm graduating in May, making 85k in Chicago, $20k in student loans, want to move "
    "to Seattle by September 2027. I have $1,000 saved.",
    "I live in Jersey City, NJ and just got a job offer in New York City paying 85k. "
    "I want to move by August 2027 and have $2,000 saved.",
    "I'm in Austin, Texas and got a 72k job in Denver, Colorado. I'd like a 1-bedroom "
    "and want to move by July 2027. I have no savings yet.",
]

CACHE_PATH = Path(__file__).parent / "demo_cache.json"
ATTEMPTS = 3  # LLM output varies run to run; retry before giving up on an input


def _is_plan(result: dict) -> bool:
    return not result.get("follow_up_question") and result.get("monthly_savings") is not None


def main() -> int:
    cache, failed = {}, []
    for situation in DEMO_INPUTS:
        print(f"\n>>> {situation}")
        for attempt in range(1, ATTEMPTS + 1):
            try:
                result = build_plan(situation)
            except Exception as e:
                print(f"  attempt {attempt}: error: {e}")
                continue
            if _is_plan(result):  # only cache real plans, not follow-up questions
                print(json.dumps(result, indent=2))
                cache[situation.strip()] = result
                break
            print(f"  attempt {attempt}: no plan, follow-up was: {result.get('follow_up_question')}")
        else:
            failed.append(situation)

    if failed:
        print(f"\n{len(failed)} input(s) did not produce a plan; demo_cache.json NOT written:")
        for s in failed:
            print(f"  - {s}")
        return 1

    CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n")
    print(f"\nSaved {len(cache)} demo responses to {CACHE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
