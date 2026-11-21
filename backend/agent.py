"""Groq tool-calling agent that turns a plain-English situation into a plan.

Rule: the model never does arithmetic. It parses text and chooses tools;
compute_plan / compare_options in tools.py produce every number in the response.
"""

import inspect
import json
import os
import re
from datetime import date
import time
import types
from pathlib import Path
from typing import Any, Callable, Literal, Union, get_args, get_origin, get_type_hints, is_typeddict

from dotenv import load_dotenv
from groq import APIStatusError, Groq, RateLimitError

from tools import TOOLS

load_dotenv(Path(__file__).parent / ".env")  # backend/.env, wherever this is imported from
MODEL = os.environ["GROQ_MODEL"]
# Tried in order when MODEL is rate-limited (each Groq model has its own token limits).
# Comma-separated; models your Groq org has blocked are skipped.
FALLBACK_MODELS = [m.strip() for m in os.environ.get("GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b").split(",")
                   if m.strip() and m.strip() != MODEL]
MAX_RETRY_WAIT = 15  # seconds; per-minute limits usually clear within a few seconds
client = Groq(api_key=os.environ["GROQ_API_KEY"])


def _retry_after(err: RateLimitError) -> float | None:
    try:
        return float(err.response.headers.get("retry-after", ""))
    except (TypeError, ValueError):
        return None


def _chat(**kwargs):
    """One Groq call. On a rate limit: wait and retry MODEL once if Groq says it's a short wait
    (per-minute limit), then try each fallback model. Blocked or unavailable fallbacks are skipped.
    If nothing works, the original rate-limit error is raised."""
    try:
        return client.chat.completions.create(model=MODEL, **kwargs)
    except RateLimitError as first:
        wait = _retry_after(first)
        if wait is not None and wait <= MAX_RETRY_WAIT:
            time.sleep(wait + 0.5)
            try:
                return client.chat.completions.create(model=MODEL, **kwargs)
            except RateLimitError:
                pass
        for model in FALLBACK_MODELS:
            try:
                return client.chat.completions.create(model=model, **kwargs)
            except (RateLimitError, APIStatusError):  # limited too, blocked (403) or unknown (404)
                continue
        raise first

MAX_TURNS = 8

_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean", dict: "object", list: "array"}


def _type_schema(tp: Any) -> dict:
    """JSON schema for a type hint: primitives, list[X], Literal enums, TypedDicts, X | None."""
    origin, args = get_origin(tp), get_args(tp)
    if origin in (Union, types.UnionType):
        inner = [a for a in args if a is not type(None)]
        schema = _type_schema(inner[0])
        if type(None) in args:
            t = schema.get("type", "object")
            schema["type"] = [t, "null"] if isinstance(t, str) else t
        return schema
    if origin is Literal:
        return {"type": "string", "enum": list(args)}
    if origin is list:
        return {"type": "array", "items": _type_schema(args[0]) if args else {}}
    if is_typeddict(tp):
        hints = get_type_hints(tp)
        return {
            "type": "object",
            "properties": {k: _type_schema(v) for k, v in hints.items()},
            "required": sorted(tp.__required_keys__),
        }
    return {"type": _JSON_TYPES.get(tp, "string")}


def _empty_contract(follow_up: str | None = None) -> dict:
    return {
        "monthly_savings": None,
        "total_needed": None,
        "deadline": None,
        "profile": None,
        "move_in_costs": None,
        "monthly_budget": None,
        "current_budget": None,
        "warnings": [],
        "follow_up_question": follow_up,
        "options": [],
    }


def function_to_tool(fn: Callable) -> dict:
    """Convert a Python function into an OpenAI-style tool definition.

    The description is the docstring summary; parameter descriptions come from
    the docstring's "Args:" section; types come from type hints.
    """
    doc = inspect.getdoc(fn) or ""
    summary, _, args_block = doc.partition("Args:")
    arg_docs = dict(re.findall(r"^\s*(\w+):\s*(.+)$", args_block, re.MULTILINE))
    hints = get_type_hints(fn)

    properties, required = {}, []
    for name, param in inspect.signature(fn).parameters.items():
        schema = _type_schema(hints.get(name, str))
        if param.default is inspect.Parameter.empty:
            required.append(name)
        elif isinstance(schema.get("type"), str):
            schema["type"] = [schema["type"], "null"]  # optional: model may send null; _run_tool drops it
        properties[name] = {**schema, "description": arg_docs.get(name, "")}

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": " ".join(summary.split()),
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOL_SCHEMAS = [function_to_tool(fn) for fn in TOOLS]
TOOL_FUNCS: dict[str, Callable] = {fn.__name__: fn for fn in TOOLS}

SYSTEM_PROMPT = f"""You are a relocation savings planner. Today is {date.today().isoformat()}.

The user describes their situation. Extract: salary (or several job offers with city and
salary), current city, target city and its two-letter state, move date, bedrooms, current
savings, lifestyle preferences (nightlife, outdoors, transit, food, weather), and their finances
NOW: current salary, current rent, monthly bills, monthly debt payments, and other monthly spending.

Choose ONE planning tool:
- compare_options: the user has multiple job offers, is choosing between cities, asks where to
  move / for recommendations, or mentions lifestyle preferences. Pass offers if they listed
  them; otherwise pass salary, plus work_city if they named where they'll work or an area they
  prefer (it then ranks towns within radius_miles, default 50; pass a different radius only if
  the user gives one). Omit work_city only for remote work with no preferred area. Map
  preferences to the allowed tags (e.g. "bars and clubs" -> nightlife, "hiking" -> outdoors,
  "no car" -> transit).
  ALSO use compare_options (with work_city = the job's city) whenever the user wants a suburb,
  to live "nearby", "outside the city", in "the <city> area", or asks where to live. Set
  suburbs_only true for "suburb" / "outside the city".
- compute_plan: one specific town to live in, with no preferences, alternatives or area request.

Rules:
- You NEVER do arithmetic, NEVER rank cities yourself, and NEVER invent dollar figures or scores.
  Every number comes from tools.
- Convert a vague move date to YYYY-MM-DD (e.g. "September 2027" -> "2027-09-01"). If no year
  is given, use the next occurrence of that month after today.
- Required: move date, and a salary (or each offer's salary). compute_plan also needs a target
  city. If a required detail is missing, do NOT call a planning tool; ask one short follow-up
  question for the missing ones.
- Never ask about optional details (current city, bedrooms, savings, preferences, current
  finances). If not given, omit them and the defaults apply. Never guess current_city.
- Pass money amounts exactly as the user stated them, converted only to plain numbers
  ("85k" -> 85000, "$1.2k" -> 1200). If they state a yearly amount for a monthly field, or a
  weekly one, omit the field rather than converting it. If they give a debt balance but no
  monthly payment, pass debt_balance and omit monthly_debt_payments; never estimate a payment.
- If the user mentions only ONE salary, it is the new job's salary: never ask for the salary
  again. Pass it as current_salary too only if they clearly say they earn it now at a current
  job they're leaving. If they're a student with no income, pass current_salary 0.
- If the user states the rent they expect to pay in the new city, pass it as target_rent.
- Roommates: "a roommate" -> roommates 1, "two roommates" -> 2. Pass it to whichever planning tool
  you use.
- Follow-ups ("what if I get a roommate?", "what about the Boston area?", "move in December
  instead"): call a planning tool again with ALL earlier details plus the change. Never repeat
  the previous plan unchanged. Later messages override earlier ones.
- Roommates are cumulative across the conversation: "a roommate" = 1; "another roommate" /
  "add one more" = the current count + 1; "2 roommates" / "3 roommates" = exactly that number;
  "no roommates" / "live alone" = 0. Count carefully before calling the tool.
- If a tool returns an error, ask the user a follow-up question that would resolve it. Never ask
  the same question twice: if the user already answered it, call the tool with their answer.
- Every US town works, even small ones (the tools use the nearest town with rent data). Never ask
  the user for rent just because a town is small."""

FINAL_INSTRUCTION = """You could not build a plan. Reply with a JSON object with exactly one key,
follow_up_question: one short question asking for the missing details. Output only the JSON."""

PLAN_KEYS = ("monthly_savings", "total_needed", "deadline", "profile", "move_in_costs", "monthly_budget",
             "current_budget", "warnings", "follow_up_question")


def _plan_from_options(result: dict) -> dict:
    """Top-level fields = the #1 option's plan; all options go in "options"."""
    top = result["options"][0]
    plan = {k: top[k] for k in PLAN_KEYS}
    plan["warnings"] = list(plan["warnings"]) + [
        f"No rent data for {city}; not compared" for city in result.get("skipped", [])
    ]
    plan["options"] = result["options"]
    return plan


def _run_tool(name: str, raw_args: str) -> Any:
    fn = TOOL_FUNCS.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    try:
        args = {k: v for k, v in json.loads(raw_args or "{}").items() if v is not None}
        return fn(**args)  # dropped nulls fall back to the function's defaults
    except Exception as e:  # report bad arguments back to the model instead of crashing
        return {"error": f"{type(e).__name__}: {e}"}


def build_plan(situation: str | list[dict]) -> dict:
    """Run the tool-calling loop and return a dict matching the /plan contract.

    situation is the user's text, or a whole chat as [{"role": "user"|"assistant", "content"}]
    so follow-ups ("add another roommate") are read in order.
    """
    if isinstance(situation, str):
        convo = [{"role": "user", "content": situation}]
    else:
        convo = [{"role": m["role"], "content": str(m.get("content", ""))} for m in situation
                 if m.get("role") in ("user", "assistant") and m.get("content")]
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}, *convo]
    plan: dict | None = None  # last successful planning-tool result: the source of truth

    # 1) Tool loop: keep going until the model answers without requesting tools.
    for _ in range(MAX_TURNS):
        resp = _chat(messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto", temperature=0)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            break

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            result = _run_tool(tc.function.name, tc.function.arguments)
            if isinstance(result, dict) and "error" not in result:
                if tc.function.name == "compute_plan":
                    plan = {**result, "options": []}
                elif tc.function.name == "compare_options":
                    plan = _plan_from_options(result)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
        if plan is not None:
            break  # Python has the answer; another model turn would only cost tokens
    else:
        if plan is None:
            return _empty_contract("Sorry, I couldn't build a plan. Could you restate your salary, target city and move date?")

    # 2) A planning tool succeeded: Python's result is the answer (numbers never pass through
    #    the model). Skipping the extra LLM call also saves Groq rate-limit tokens.
    if plan is not None:
        return plan

    # 3) No plan: ask for the follow-up question in JSON mode (no tools; Groq won't combine them).
    messages.append({"role": "user", "content": FINAL_INSTRUCTION})
    resp = _chat(messages=messages, response_format={"type": "json_object"}, temperature=0)
    try:
        answer = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        answer = {}

    follow_up = answer.get("follow_up_question") or (
        "Could you tell me your salary, the city you're moving to, and when you want to move?"
    )
    return _empty_contract(str(follow_up))


if __name__ == "__main__":
    cases = [
        "I'm graduating in May, making 85k in Chicago, $20k in student loans, want to move to "
        "Seattle by September 2027. I have $1,000 saved.",
        "I have two offers: 75k in Austin and 110k in New York. Moving from Chicago in August "
        "2027, and I care about nightlife.",
        "I work remote making 80k and want somewhere with great nightlife and food. "
        "Moving next June.",
        "Got a 95k job in Seattle starting August 2027. Where should I live nearby? I love hiking "
        "and want to keep rent low.",
        "I want to move to Seattle sometime next year.",  # missing salary and exact date
    ]
    for situation in cases:
        print(f"\n>>> {situation}")
        print(json.dumps(build_plan(situation), indent=2))
