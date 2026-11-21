import copy
import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import build_plan

logger = logging.getLogger("uvicorn.error")

# Saved responses for the demo inputs, keyed by exact situation text.
# Regenerate with: python build_demo_cache.py
DEMO_CACHE_PATH = Path(__file__).parent / "demo_cache.json"


def _load_demo_cache() -> dict:
    # Read on every request so a regenerated cache is picked up without a restart.
    try:
        return json.loads(DEMO_CACHE_PATH.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read %s; ignoring demo cache", DEMO_CACHE_PATH)
        return {}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PlanRequest(BaseModel):
    situation: str

# Fallback returned if the LLM call fails or returns something off-contract.
MOCK_PLAN = {
    "monthly_savings": 950,
    "total_needed": 11400,
    "deadline": "2027-06-01",
    "profile": None,
    "move_in_costs": {
        "first_month": 2400,
        "deposit": 2400,
        "movers": 1200,
        "furniture": 1500,
    },
    "monthly_budget": {"rent": 2400, "take_home": 5100},
    "current_budget": None,
    "warnings": ["Rent is 47% of take-home pay"],
    "follow_up_question": None,
    "options": [],
}

FALLBACK_WARNING = "Live planning is unavailable right now; these are sample numbers, not your plan."


def _fallback() -> dict:
    result = copy.deepcopy(MOCK_PLAN)  # deep copy so we never mutate the shared mock
    result["warnings"].append(FALLBACK_WARNING)
    return result


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/plan")
def plan(req: PlanRequest):
    cached = _load_demo_cache().get(req.situation.strip())
    if cached is not None:
        logger.info("Serving /plan from demo cache")
        return cached

    try:
        result = build_plan(req.situation)
    except Exception:
        logger.exception("build_plan failed; returning mock plan")
        return _fallback()

    if not isinstance(result, dict) or set(result) != set(MOCK_PLAN):
        logger.error("build_plan returned off-contract result; returning mock plan: %r", result)
        return _fallback()

    return result
