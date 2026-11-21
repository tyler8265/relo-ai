"""
Connects the web UI to the real backend in backend/ (agent.build_plan), in three layers:

  1. backend/demo_cache.json: saved real answers for the demo inputs (exact text match).
     Works with no API key and any Python version, so the demo can't be broken by a rate limit.
  2. The live agent: backend/agent.build_plan(situation). Needs Python 3.11+, the backend's
     packages (groq, python-dotenv) and GROQ_API_KEY / GROQ_MODEL in backend/.env.
  3. If the live agent can't load or fails: the mock agent, labeled as offline in its warnings.

The backend takes one situation string, so the chat's user messages are joined into one.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
CACHE_PATH = BACKEND / "demo_cache.json"

FORCE_MOCK = os.environ.get("RELO_MOCK") == "1"
HAS_BACKEND = (BACKEND / "agent.py").exists() and not FORCE_MOCK

_build_plan = None
_agent_error: str | None = None
_loaded = False


def _load_agent() -> None:
    """Import backend/agent.py once. Records why it can't run instead of raising."""
    global _build_plan, _agent_error, _loaded
    if _loaded:
        return
    _loaded = True
    if not HAS_BACKEND:
        _agent_error = "mock mode" if FORCE_MOCK else "no backend/agent.py"
        return
    if sys.version_info < (3, 11):
        _agent_error = f"the backend needs Python 3.11+, this is {sys.version.split()[0]}"
        return
    try:
        if str(BACKEND) not in sys.path:
            sys.path.insert(0, str(BACKEND))
        from agent import build_plan  # noqa: PLC0415  (backend/agent.py)
        _build_plan = build_plan
    except KeyError as e:
        _agent_error = f"{e.args[0]} is not set (add it to backend/.env)"
    except ModuleNotFoundError as e:
        _agent_error = f"missing package {e.name!r} (pip install -r backend requirements)"
    except Exception as e:  # noqa: BLE001
        _agent_error = f"{type(e).__name__}: {e}"


def status() -> dict:
    _load_agent()
    return {"backend": HAS_BACKEND, "live": _build_plan is not None, "reason": _agent_error}


def _situation(messages: list[dict]) -> str:
    return " ".join(m["content"].strip() for m in messages if m.get("role") == "user" and m.get("content"))


def _cached(situation: str) -> dict | None:
    try:
        return json.loads(CACHE_PATH.read_text()).get(situation.strip())
    except (OSError, json.JSONDecodeError):
        return None


def _mock(messages: list[dict], why: str) -> tuple[dict, str]:
    from mock_agent import respond  # noqa: PLC0415

    raw = copy.deepcopy(respond(messages))
    if HAS_BACKEND and not raw.get("follow_up_question"):
        raw.setdefault("warnings", []).append({
            "level": "info",
            "text": f"The live planner is offline ({why}). These are placeholder numbers, not your plan.",
        })
    return raw, "mock"


def respond(messages: list[dict]) -> tuple[dict, str]:
    """Returns (backend-format response, source) where source is cache, live or mock."""
    if not HAS_BACKEND:
        return _mock(messages, _agent_error or "no backend")

    situation = _situation(messages)
    hit = _cached(situation)
    if hit is not None:
        return copy.deepcopy(hit), "cache"

    _load_agent()
    if _build_plan is None:
        return _mock(messages, _agent_error or "unavailable")
    try:
        result = _build_plan(situation)
    except Exception as e:  # noqa: BLE001  (rate limits, network) — keep the demo alive
        traceback.print_exc()
        return _mock(messages, f"{type(e).__name__}")
    if not isinstance(result, dict):
        return _mock(messages, "unexpected response")
    return result, "live"
