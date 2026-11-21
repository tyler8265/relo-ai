"""
Stand-in for the Gemini agent so the UI can be built and demoed with no API key.
Follows the contract in contract.py. Swap it out by setting USE_MOCK = False in app.py.

It does crude keyword parsing over the whole chat (later messages override earlier
ones), so follow-ups like "what if I move in December?" or "skip the roommate" work.
Numbers are rough placeholders, NOT real data.
"""
from __future__ import annotations

import math
import re
from datetime import date

# Placeholder 1BR rents; the tools lane replaces these with HUD FMR data.
RENT_1BR = {
    "new york": ("New York, NY", 2650, 0.065),
    "nyc": ("New York, NY", 2650, 0.065),
    "san francisco": ("San Francisco, CA", 2900, 0.06),
    "seattle": ("Seattle, WA", 2150, 0.0),
    "austin": ("Austin, TX", 1550, 0.0),
    "chicago": ("Chicago, IL", 1750, 0.0495),
    "boston": ("Boston, MA", 2600, 0.05),
    "denver": ("Denver, CO", 1800, 0.044),
    "los angeles": ("Los Angeles, CA", 2300, 0.06),
    "atlanta": ("Atlanta, GA", 1650, 0.055),
    "miami": ("Miami, FL", 2200, 0.0),
    "washington": ("Washington, DC", 2100, 0.06),
}

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"]
    )
}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})


def _money(text: str) -> float | None:
    m = re.match(r"\$?\s*([\d,.]+)\s*(k|K)?", text)
    if not m:
        return None
    val = float(m.group(1).replace(",", ""))
    return val * 1000 if m.group(2) else val


def _parse(messages: list[dict]) -> dict:
    p: dict = {"roommate": False, "bedrooms": 1, "monthly_bills": 400, "current_savings": 0}
    for msg in messages:
        if msg["role"] != "user":
            continue
        t = msg["content"].lower()

        if m := re.search(r"(?:making|salary|earn|paying|offer)\D{0,15}(\$?[\d,.]+\s*k?)", t):
            p["salary"] = _money(m.group(1))
        elif m := re.search(r"(\$?[\d,.]+\s*k)\b", t):
            p.setdefault("salary", _money(m.group(1)))

        if m := re.search(r"(\$?[\d,.]+\s*k?)\s*(?:in|of)?\s*(?:student )?(?:loans?|debt)", t):
            p["debt"] = _money(m.group(1))
        if re.search(r"no (?:student )?(?:loans|debt)", t):
            p["debt"] = 0
        if m := re.search(r"(\$?[\d,.]+\s*k?)\s*(?:saved|in savings)", t):
            p["current_savings"] = _money(m.group(1))
        if m := re.search(r"(\$?[\d,.]+\s*k?)\s*(?:a|per|/)\s*month (?:in )?bills", t):
            p["monthly_bills"] = _money(m.group(1))

        new_target = None
        for k in sorted((k for k in RENT_1BR if k in t), key=t.find):
            if re.search(rf"(?:move|moving|relocat\w*|go|going)\s+to\s+{k}|(?:job|offer|role|position|work)\s+in\s+{k}", t):
                new_target = k
            elif re.search(rf"\b(?:in|from|live in|living in|based in)\s+{k}", t):
                p["current_city"] = k
            elif new_target is None:
                new_target = k
        if new_target:
            p["target_city"] = new_target

        if re.search(r"\b(skip|no|without|don't want)( the| a)? roommates?", t):
            p["roommate"] = False
        elif "roommate" in t:
            p["roommate"] = True

        for name, num in MONTHS.items():
            if re.search(rf"\b(?:by|in|move in|start in|until)\s+{name}\b", t):
                today = date.today()
                year = today.year if num > today.month else today.year + 1
                p["deadline"] = date(year, num, 1)
    return p


def respond(messages: list[dict]) -> dict:
    p = _parse(messages)

    if "target_city" not in p:
        return {"follow_up_question": "Which city are you moving to?"}
    if "salary" not in p:
        return {"follow_up_question": "What's the salary for the new job? A rough number is fine."}
    if "deadline" not in p:
        return {"follow_up_question": "When do you want to move? A month is enough (for example, \"by September\")."}

    target_city, rent_full, state_rate = RENT_1BR[p["target_city"]]
    rent = round(rent_full * (0.6 if p["roommate"] else 1.0))
    current_city = RENT_1BR.get(p.get("current_city", ""), ("Unknown",))[0]

    salary = p["salary"]
    take_home = round(salary * (1 - 0.22 - state_rate - 0.0765) / 12)
    debt = p.get("debt", 0) or 0
    debt_payment = round(debt / 120 * 1.3) if debt else 0

    costs = {
        "first_month": rent,
        "deposit": rent,
        "movers": 1800 if current_city != "Unknown" else 2200,
        "furniture": 1200 if p["roommate"] else 2000,
        "paycheck_gap": rent // 2 + p["monthly_bills"],
    }
    if "new york" in target_city.lower():
        costs["broker_fee"] = round(rent_full * 12 * 0.15 * (0.6 if p["roommate"] else 1))

    total = sum(costs.values())
    today = date.today()
    deadline = p["deadline"]
    months = max(1, (deadline.year - today.year) * 12 + deadline.month - today.month)
    monthly = math.ceil(max(0, total - p["current_savings"]) / months / 10) * 10

    warnings = []
    ratio = rent / take_home
    if ratio > 0.30:
        warnings.append(f"Rent would be {ratio:.0%} of take-home pay. The usual guideline is under 30%.")
    if "new york" in target_city.lower() and salary < rent_full * 40:
        warnings.append({"level": "error",
                         "text": f"Many NYC landlords want a salary of 40x rent (${rent_full * 40:,.0f}). "
                                 f"At ${salary:,.0f} you may need a guarantor."})
    if debt:
        warnings.append({"level": "info",
                         "text": f"Your ${debt:,.0f} in debt costs about ${debt_payment:,}/month, already included in the budget."})
    if monthly > take_home * 0.4:
        warnings.append({"level": "error",
                         "text": f"Saving ${monthly:,}/month is aggressive. Consider pushing the move date back."})

    what = "with a roommate" if p["roommate"] else "living alone"
    # Same shape as the real backend (see contract.py), plus the optional fields.
    return {
        "monthly_savings": monthly,
        "total_needed": total,
        "deadline": deadline.isoformat(),
        "move_in_costs": costs,
        "monthly_budget": {"rent": rent, "take_home": take_home,
                           "bills": p["monthly_bills"], "debt_payment": debt_payment},
        "warnings": warnings,
        "follow_up_question": None,
        "months_to_save": months,
        "message": f"Here's your plan for moving to {target_city} by {deadline:%B %Y}, {what}. "
                   f"Save ${monthly:,}/month for {months} months to reach ${total:,}.",
        "profile": {
            "salary": salary, "current_city": current_city, "target_city": target_city,
            "debt": debt, "monthly_bills": p["monthly_bills"],
            "current_savings": p["current_savings"], "roommate": p["roommate"],
        },
    }
