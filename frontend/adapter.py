"""
Converts the backend's response (format in contract.py) into what the UI renders.
Optional fields the backend may leave out get safe defaults here, so the UI never has to check.
"""
from __future__ import annotations

from datetime import date

COST_LABELS = {
    "first_month": "First month's rent",
    "deposit": "Security deposit",
    "movers": "Movers / truck",
    "furniture": "Furniture & setup",
    "paycheck_gap": "Gap before first paycheck",
    "expenses_before_first_paycheck": "Expenses before first paycheck",
    "broker_fee": "Broker fee",
    "emergency_buffer": "Emergency buffer",
}


def months_until(deadline: date, today: date | None = None) -> int:
    today = today or date.today()
    return max(1, (deadline.year - today.year) * 12 + deadline.month - today.month)


def _plan(raw: dict, profile: dict) -> dict:
    """One plan (the top level, or one city option) in the UI's shape."""
    deadline = date.fromisoformat(raw["deadline"])
    months = raw.get("months_to_save") or months_until(deadline)

    costs = raw.get("move_in_costs") or {}
    if isinstance(costs, dict):
        costs = [{"label": COST_LABELS.get(k, k.replace("_", " ").capitalize()), "amount": v}
                 for k, v in costs.items()]
    costs = [c for c in costs if c.get("amount")]  # a $0 line adds nothing to a breakdown

    warnings = [w if isinstance(w, dict) else {"level": "warning", "text": str(w)}
                for w in raw.get("warnings") or []]

    mb = raw.get("monthly_budget") or {}
    budget = {
        "take_home": mb.get("take_home", 0),
        "rent": mb.get("rent", 0),
        "bills": mb.get("bills") or 0,
        "debt_payment": mb.get("debt_payment", mb.get("debt_payments")) or 0,
        "spending": mb.get("spending") or 0,
    }
    if "leftover" in mb:
        budget["leftover"] = mb["leftover"]

    total, monthly = raw["total_needed"], raw["monthly_savings"]

    # Sanity check on the backend's numbers: does the monthly amount actually reach the goal?
    # Only checkable when the response says what's already saved: the backend subtracts savings
    # without echoing them back, so without that figure any "gap" may just be money already saved.
    reached = profile.get("current_savings", 0) + monthly * months
    shortfall = max(0, total - reached) if "current_savings" in profile else 0
    if shortfall > monthly:
        warnings.append({
            "level": "error",
            "text": f"Saving ${monthly:,.0f}/month for {months} months reaches ${reached:,.0f} by {deadline:%B %Y}, "
                    f"${shortfall:,.0f} short of the ${total:,.0f} goal unless you already have that much saved.",
        })
    else:
        shortfall = 0

    current = raw.get("current_budget") or None
    if current:
        current = {"take_home": current.get("take_home", 0),
                   "surplus": current.get("surplus", current.get("leftover", 0))}

    return {
        "profile": profile,
        "deadline": deadline.isoformat(),
        "target_total": total,
        "monthly_savings": monthly,
        "months_to_save": months,
        "move_in_costs": costs,
        "monthly_budget": budget,
        "warnings": warnings,
        "shortfall": shortfall,
        "current_budget": current,
    }


def _option(opt: dict, base_profile: dict) -> dict:
    city = ", ".join(x for x in (opt.get("city"), opt.get("state")) if x)
    profile = {**base_profile, "target_city": city}
    if opt.get("salary"):
        profile["salary"] = opt["salary"]
    return {
        "rank": opt.get("rank"),
        "city": city,
        "score": opt.get("score"),
        "salary": opt.get("salary"),
        "work_city": opt.get("work_city"),
        "miles_from_work": opt.get("miles_from_work") or 0,
        "reasons": [str(r) for r in opt.get("reasons") or []],
        "score_breakdown": [
            {"factor": str(b.get("factor", "")), "points": b.get("points"), "weight": b.get("weight"),
             "detail": str(b.get("detail", ""))}
            for b in opt.get("score_breakdown") or []
        ],
        "plan": _plan(opt, profile),
    }


def normalize(raw: dict) -> dict:
    """Returns {"type": "question", "message"} or {"type": "plan", "message", "plan", "options"}."""
    if raw.get("follow_up_question"):
        return {"type": "question", "message": raw["follow_up_question"]}
    if not raw.get("deadline") or raw.get("total_needed") is None or raw.get("monthly_savings") is None:
        return {"type": "question",
                "message": "I couldn't build a plan from that. What's your salary, where are you moving, and when?"}

    base = dict(raw.get("profile") or {})
    options = [_option(o, base) for o in raw.get("options") or [] if o.get("deadline")]
    options.sort(key=lambda o: o["rank"] if o["rank"] is not None else 99)

    profile = dict(base)
    if options and "target_city" not in profile:
        profile["target_city"] = options[0]["city"]
        if options[0]["salary"] and "salary" not in profile:
            profile["salary"] = options[0]["salary"]
    plan = _plan(raw, profile)

    total, monthly, deadline = plan["target_total"], plan["monthly_savings"], date.fromisoformat(plan["deadline"])
    if raw.get("message"):
        message = raw["message"]
    elif len(options) > 1:
        message = (f"I found **{len(options)} places** that fit. **{options[0]['city']}** ranks first: you need "
                   f"**${total:,.0f} by {deadline:%B %Y}**, so save **${monthly:,.0f}/month** starting now. "
                   f"Compare the others above the pass.")
    else:
        message = (f"You need **${total:,.0f} by {deadline:%B %Y}**. "
                   f"That means saving **${monthly:,.0f}/month** starting now.")
    return {"type": "plan", "message": message, "plan": plan, "options": options}
