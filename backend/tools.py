"""Tool functions the LLM can call. All numbers and all arithmetic live here.

agent.py builds tool schemas from these functions' names, type hints and
docstrings ("Args:" sections become parameter descriptions), so keep them accurate.

Data: rents, populations and coordinates for ~1,100 US places come from the Census
(see data/places.json and build_places.py). Taxes, move costs and lifestyle scores are
still approximations, noted where they're defined.
"""

import json
import math
from datetime import date
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

# --- Places -----------------------------------------------------------------------------
_DATA = json.loads((Path(__file__).parent / "data" / "places.json").read_text())
RENT_SOURCE = _DATA["source"]


def _key(name: str, state: str) -> str:
    return f"{name.strip().lower()}|{state.strip().upper()}"


_PLACES: dict[str, dict] = {_key(p["name"], p["state"]): p for p in _DATA["places"]}
# name -> keys in every state with that name, most populous first (for "Portland" etc.)
_BY_NAME: dict[str, list[str]] = {}
for _k, _p in sorted(_PLACES.items(), key=lambda kv: -kv[1]["population"]):
    _BY_NAME.setdefault(_p["name"].lower(), []).append(_k)

_CITY_ALIASES = {
    "new york city": "new york", "nyc": "new york", "manhattan": "new york",
    "sf": "san francisco", "la": "los angeles", "honolulu": "urban honolulu",
    "washington dc": "washington", "washington d.c.": "washington", "dc": "washington",
    "vegas": "las vegas", "philly": "philadelphia",
}
_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
_NYC = _key("New York", "NY")


def _state_code(state: str | None) -> str | None:
    if not state:
        return None
    s = state.strip().lower().replace(".", "")
    return _STATE_NAMES.get(s, s.upper() if len(s) == 2 else None)


def _resolve(city: str, state: str | None = None) -> str | None:
    """Find a place key for "Seattle", "Seattle, WA" or ("Portland", "ME"). None if unknown."""
    name, _, tail = city.partition(",")
    name = name.strip().lower()
    st = _state_code(tail) or _state_code(state)
    # Real names win over aliases, so "Manhattan, KS" isn't treated as New York.
    for n in (name, _CITY_ALIASES.get(name)):
        candidates = [k for k in _BY_NAME.get(n or "", []) if not st or k.endswith(f"|{st}")]
        if candidates:
            return candidates[0]
    return None


def _miles_between(a: str, b: str) -> float:
    """Straight-line (great-circle) distance in miles between two place keys."""
    pa, pb = _PLACES[a], _PLACES[b]
    p1, p2 = math.radians(pa["lat"]), math.radians(pb["lat"])
    dp, dl = p2 - p1, math.radians(pb["lon"] - pa["lon"])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


# --- Lifestyle --------------------------------------------------------------------------
# Scores 1-5 for (nightlife, outdoors, transit, food, weather). HAND-ASSIGNED ESTIMATES for a
# few metros and suburbs only, not sourced data; shown to users as "(estimate)". Places not
# listed get a neutral 3 and are shown as "no data".
Lifestyle = Literal["nightlife", "outdoors", "transit", "food", "weather"]
_LIFESTYLE_KEYS = ("nightlife", "outdoors", "transit", "food", "weather")
_NEUTRAL = 3
_LIFESTYLE_EST = {
    ("Seattle", "WA"): (3, 5, 3, 4, 2), ("Bellevue", "WA"): (2, 4, 2, 4, 2),
    ("Redmond", "WA"): (1, 5, 2, 3, 2), ("Renton", "WA"): (1, 4, 2, 3, 2),
    ("Tacoma", "WA"): (2, 4, 2, 3, 2), ("Everett", "WA"): (1, 4, 2, 2, 2),
    ("Chicago", "IL"): (4, 2, 4, 5, 2), ("Evanston", "IL"): (2, 3, 4, 4, 2),
    ("Oak Park", "IL"): (2, 2, 4, 3, 2), ("Naperville", "IL"): (2, 3, 2, 3, 2),
    ("Schaumburg", "IL"): (1, 2, 1, 3, 2), ("Gary", "IN"): (1, 3, 2, 1, 2),
    ("New York", "NY"): (5, 2, 5, 5, 3), ("Jersey City", "NJ"): (3, 2, 4, 4, 3),
    ("Hoboken", "NJ"): (4, 2, 4, 4, 3), ("Newark", "NJ"): (2, 1, 4, 3, 3),
    ("Yonkers", "NY"): (1, 3, 3, 3, 3), ("Stamford", "CT"): (2, 3, 3, 3, 3),
    ("San Francisco", "CA"): (4, 4, 4, 5, 4), ("Oakland", "CA"): (4, 4, 4, 4, 4),
    ("Berkeley", "CA"): (3, 4, 4, 4, 4), ("Daly City", "CA"): (1, 3, 3, 3, 3),
    ("Fremont", "CA"): (1, 3, 2, 3, 4), ("San Jose", "CA"): (2, 3, 2, 4, 5),
    ("Austin", "TX"): (5, 3, 1, 4, 4), ("Round Rock", "TX"): (2, 3, 1, 3, 4),
    ("Cedar Park", "TX"): (1, 3, 1, 3, 4), ("Pflugerville", "TX"): (1, 3, 1, 2, 4),
    ("Georgetown", "TX"): (1, 4, 1, 2, 4), ("San Marcos", "TX"): (3, 4, 1, 2, 4),
    ("Boston", "MA"): (3, 3, 4, 4, 2), ("Cambridge", "MA"): (3, 3, 4, 4, 2),
    ("Somerville", "MA"): (3, 2, 4, 4, 2), ("Quincy", "MA"): (1, 3, 4, 3, 2),
    ("Worcester", "MA"): (2, 3, 2, 3, 2), ("Providence", "RI"): (3, 3, 2, 4, 2),
    ("Denver", "CO"): (3, 5, 2, 3, 4), ("Boulder", "CO"): (3, 5, 2, 3, 4),
    ("Aurora", "CO"): (1, 4, 2, 3, 4), ("Lakewood", "CO"): (1, 5, 2, 2, 4),
    ("Littleton", "CO"): (1, 5, 2, 2, 4),
    ("Los Angeles", "CA"): (4, 4, 2, 5, 5), ("Santa Monica", "CA"): (3, 5, 2, 4, 5),
    ("Pasadena", "CA"): (2, 4, 2, 4, 5), ("Burbank", "CA"): (2, 3, 2, 3, 5),
    ("Long Beach", "CA"): (3, 4, 2, 4, 5), ("Irvine", "CA"): (1, 4, 1, 4, 5),
    ("Atlanta", "GA"): (4, 2, 2, 4, 4),
    ("Sandy Springs", "GA"): (1, 3, 2, 3, 4), ("Marietta", "GA"): (1, 3, 1, 3, 4),
    ("Alpharetta", "GA"): (2, 3, 1, 3, 4),
    ("Miami", "FL"): (5, 3, 2, 4, 5), ("Coral Gables", "FL"): (2, 3, 2, 4, 5),
    ("Hialeah", "FL"): (1, 2, 2, 3, 5), ("Hollywood", "FL"): (2, 4, 2, 3, 5),
    ("Fort Lauderdale", "FL"): (4, 4, 2, 4, 5),
}
_LIFESTYLE = {_key(n, s): v for (n, s), v in _LIFESTYLE_EST.items()}

# --- Taxes ------------------------------------------------------------------------------
# Flat state income tax approximations (0 = no state income tax). Taxed where the person lives.
_STATE_RATE = {
    "AK": 0.0, "FL": 0.0, "NV": 0.0, "NH": 0.0, "SD": 0.0, "TN": 0.0, "TX": 0.0, "WA": 0.0, "WY": 0.0,
    "AL": 0.045, "AZ": 0.025, "AR": 0.039, "CA": 0.07, "CO": 0.044, "CT": 0.05, "DE": 0.055,
    "DC": 0.065, "GA": 0.0539, "HI": 0.07, "ID": 0.058, "IL": 0.0495, "IN": 0.03, "IA": 0.038,
    "KS": 0.05, "KY": 0.04, "LA": 0.03, "ME": 0.06, "MD": 0.05, "MA": 0.05, "MI": 0.0425,
    "MN": 0.06, "MS": 0.044, "MO": 0.047, "MT": 0.059, "NE": 0.052, "NJ": 0.05, "NM": 0.045,
    "NY": 0.06, "NC": 0.0425, "ND": 0.02, "OH": 0.035, "OK": 0.0475, "OR": 0.08, "PA": 0.0307,
    "RI": 0.045, "SC": 0.06, "UT": 0.0455, "VT": 0.06, "VA": 0.0575, "WV": 0.05, "WI": 0.053,
}
_DEFAULT_STATE_RATE = 0.05
_NYC_RATE = 0.03876  # approximate top NYC resident rate

# Federal single-filer brackets (approximate) and standard deduction.
_FED_BRACKETS = [
    (11_925, 0.10), (48_475, 0.12), (103_350, 0.22), (197_300, 0.24),
    (250_525, 0.32), (626_350, 0.35), (math.inf, 0.37),
]
_STD_DEDUCTION = 15_000
_SS_WAGE_CAP = 176_100

_FURNITURE_ESTIMATE = 1500


def get_rent(city: str, bedrooms: int = 1, state: str = "") -> dict:
    """Look up median monthly rent for new leases in a US city or town (Census data).

    Args:
        city: City or town name, e.g. "Seattle" or "Portland, ME".
        bedrooms: Number of bedrooms (0 for studio).
        state: Two-letter state code, to tell apart same-named towns, e.g. "ME".
    """
    key = _resolve(city, state)
    if key is None:
        return {"city": city, "bedrooms": bedrooms, "rent": None, "error": "city not in dataset"}
    place = _PLACES[key]
    beds = str(min(max(bedrooms, 0), 3))
    rent = place["rent"].get(beds)
    if rent is None:  # no Census estimate for that size: scale from 1BR
        rent = round(place["rent"]["1"] * {"0": 0.85, "1": 1.0, "2": 1.3, "3": 1.7}[beds])
    return {"city": place["name"], "state": place["state"], "bedrooms": bedrooms, "rent": rent}


def calc_take_home(salary: float, state: str, city: str = "") -> dict:
    """Estimate monthly take-home pay after federal, FICA, state and city taxes.

    Args:
        salary: Gross annual salary in USD.
        state: Two-letter US state code where the person will live, e.g. "WA".
        city: City name, used for city income tax (e.g. New York City).
    """
    st = _state_code(state) or state.upper()
    taxable = max(0.0, salary - _STD_DEDUCTION)
    fed, lower = 0.0, 0.0
    for upper, rate in _FED_BRACKETS:
        if taxable > lower:
            fed += (min(taxable, upper) - lower) * rate
        lower = upper
    fica = min(salary, _SS_WAGE_CAP) * 0.062 + salary * 0.0145
    state_tax = taxable * _STATE_RATE.get(st, _DEFAULT_STATE_RATE)
    city_tax = taxable * _NYC_RATE if city and _resolve(city, st) == _NYC else 0.0
    annual = salary - fed - fica - state_tax - city_tax
    return {"salary": salary, "state": st, "take_home_monthly": round(annual / 12)}


def get_move_costs(from_city: str, to_city: str) -> dict:
    """Estimate the one-time cost of hiring movers between two cities.

    Args:
        from_city: City the person is moving from.
        to_city: City the person is moving to.
    """
    a, b = _resolve(from_city), _resolve(to_city)
    same = (a is not None and a == b) or from_city.strip().lower() == to_city.strip().lower()
    return {"from_city": from_city, "to_city": to_city, "movers": 500 if same else 1200}


def _months_until(deadline: date, today: date) -> int:
    return (deadline.year - today.year) * 12 + (deadline.month - today.month)


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    return date(d.year + y, m + 1, 1)


_EMERGENCY_BUFFER_MONTHS = 1  # months of new take-home pay set aside for surprises
_EXPENSES_BEFORE_PAYCHECK_MONTHS = 1      # months of non-rent expenses before the first paycheck lands


def compute_plan(
    salary: float,
    target_city: str,
    target_state: str,
    move_date: str,
    current_city: str = "",
    bedrooms: int = 1,
    current_savings: float = 0,
    current_salary: float | None = None,
    current_rent: float | None = None,
    monthly_bills: float | None = None,
    monthly_debt_payments: float | None = None,
    monthly_spending: float | None = None,
    debt_balance: float | None = None,
) -> dict:
    """Build the full savings plan, including a cushion and a check against the user's
    current budget. Does all lookups and all math; call this once you know the salary,
    target city/state and move date. Pass the user's raw inputs only, never numbers you
    computed yourself. Omit any amount the user didn't state.

    Args:
        salary: Gross annual salary in USD at the new job.
        target_city: City the person is moving to.
        target_state: Two-letter state code of the target city, e.g. "WA".
        move_date: Target move date as YYYY-MM-DD.
        current_city: City the person lives in now. Omit if unknown (a long-distance move is assumed).
        bedrooms: Bedrooms wanted (0 for studio). Default 1.
        current_savings: Money already saved toward the move, in USD. Default 0.
        current_salary: Gross annual salary the person earns NOW, in USD (0 if not working now).
        current_rent: Monthly rent the person pays NOW, in USD (0 if living rent-free).
        monthly_bills: Recurring monthly bills other than rent (phone, insurance, subscriptions, car), in USD.
        monthly_debt_payments: Monthly debt payments (student loans, car loan, credit cards), in USD. Not the balance.
        monthly_spending: Other monthly spending (groceries, eating out, gas, fun), in USD.
        debt_balance: Total debt owed, in USD, only if the user gave a balance but no monthly payment.
    """
    try:
        deadline = date.fromisoformat(move_date)
    except ValueError:
        return {"error": f"move_date must be YYYY-MM-DD, got {move_date!r}"}

    key = _resolve(target_city, target_state)
    if key is None:
        return {"error": f"no rent data for {target_city}, {target_state}"}
    place = _PLACES[key]
    rent = get_rent(place["name"], bedrooms, place["state"])["rent"]
    take_home = calc_take_home(salary, place["state"], place["name"])["take_home_monthly"]
    movers = get_move_costs(current_city, place["name"])["movers"]

    # The user's recurring costs, which follow them to the new city. Unknown -> 0, flagged below.
    bills = round(monthly_bills or 0)
    debt = round(monthly_debt_payments or 0)
    spending = round(monthly_spending or 0)
    other_expenses = bills + debt + spending

    move_in_costs = {
        "first_month": rent,
        "deposit": rent,
        "movers": movers,
        "furniture": _FURNITURE_ESTIMATE,
        # Rent for month one is already counted above; this covers everything else until payday.
        "expenses_before_first_paycheck": other_expenses * _EXPENSES_BEFORE_PAYCHECK_MONTHS,
        "emergency_buffer": take_home * _EMERGENCY_BUFFER_MONTHS,
    }
    total_needed = sum(move_in_costs.values())
    remaining = max(0, total_needed - round(current_savings))

    warnings = []
    today = date.today()
    months = _months_until(deadline, today)
    if months < 1:
        warnings.append("Move date is less than a month away; the full amount is needed now")
        months = 1
    monthly_savings = math.ceil(remaining / months)

    rent_pct = round(rent / take_home * 100) if take_home else 0
    if rent_pct > 30:
        warnings.append(f"Rent is {rent_pct}% of take-home pay (guideline: 30%)")
    if key == _NYC and salary < 40 * rent:
        warnings.append(
            f"Salary ${salary:,.0f} is below the 40x-rent rule (${40 * rent:,}) many NYC landlords use"
        )

    # After the move: does the new paycheck cover rent plus their existing costs?
    leftover = take_home - rent - other_expenses
    if leftover < 0:
        warnings.append(
            f"After the move, rent plus your current bills, debt and spending exceed take-home pay "
            f"by ${-leftover:,}/month"
        )

    missing = [label for label, v in (("bills", monthly_bills), ("debt payments", monthly_debt_payments),
                                      ("spending", monthly_spending)) if v is None]
    if missing:
        warnings.append(
            f"Your monthly {', '.join(missing)} weren't given, so they're counted as $0; "
            "add them to size your expenses before the first paycheck and your budget accurately"
        )
    if debt_balance and monthly_debt_payments is None:
        warnings.append(
            f"You mentioned ${debt_balance:,.0f} in debt; add your monthly payment to include it in the budget"
        )

    # Before the move: can they actually save monthly_savings from their current budget?
    current_budget = None
    if current_salary is not None:
        cur_key = _resolve(current_city) if current_city else None
        cur_state = _PLACES[cur_key]["state"] if cur_key else place["state"]
        cur_take_home = (calc_take_home(current_salary, cur_state, current_city)["take_home_monthly"]
                         if current_salary > 0 else 0)
        cur_rent = round(current_rent or 0)
        surplus = cur_take_home - cur_rent - other_expenses
        current_budget = {
            "take_home": cur_take_home, "rent": cur_rent, "bills": bills,
            "debt_payments": debt, "spending": spending, "surplus": surplus,
        }
        if current_rent is None:
            warnings.append("Your current rent wasn't given, so it's counted as $0")
        if surplus <= 0 and remaining > 0:
            warnings.append(
                f"You currently spend ${-surplus:,}/month more than you take home, so you can't save "
                f"toward this move without cutting costs"
                if surplus < 0 else "You currently have nothing left over each month to save toward this move"
            )
        elif monthly_savings > surplus:
            ready = _add_months(today, math.ceil(remaining / surplus))
            warnings.append(
                f"Saving ${monthly_savings:,}/month is more than the ${surplus:,}/month you have left over now. "
                f"At ${surplus:,}/month you'd have the full amount by {ready.strftime('%B %Y')}"
            )

    return {
        "monthly_savings": monthly_savings,
        "total_needed": total_needed,
        "deadline": deadline.isoformat(),
        "move_in_costs": move_in_costs,
        "monthly_budget": {
            "rent": rent, "take_home": take_home, "bills": bills,
            "debt_payments": debt, "spending": spending, "leftover": leftover,
        },
        "current_budget": current_budget,
        "warnings": warnings,
        "follow_up_question": None,
    }


class JobOffer(TypedDict):
    city: str
    salary: float
    state: NotRequired[str]


def _affordability(rent_pct: int) -> float:
    """0-100: rent at 30% of take-home or less scores 100, 60% or more scores 0."""
    return max(0.0, min(100.0, (60 - rent_pct) / 30 * 100))


def _commute(miles: float, radius: float) -> float:
    """0-100: living in the work city scores 100, at the edge of the radius scores 0."""
    return max(0.0, 100.0 * (1 - miles / radius)) if radius > 0 else 100.0


def compare_options(
    move_date: str,
    offers: list[JobOffer] | None = None,
    salary: float | None = None,
    work_city: str | None = None,
    work_state: str | None = None,
    radius_miles: float = 50,
    preferences: list[Lifestyle] | None = None,
    current_city: str = "",
    bedrooms: int = 1,
    current_savings: float = 0,
    current_salary: float | None = None,
    current_rent: float | None = None,
    monthly_bills: float | None = None,
    monthly_debt_payments: float | None = None,
    monthly_spending: float | None = None,
    debt_balance: float | None = None,
) -> dict:
    """Rank the top 3 places to live and build a savings plan for each. Use this when the
    user has several job offers, is choosing between cities, wants recommendations or
    suggestions of towns, or states lifestyle preferences. Considers every town within
    radius_miles of each work city (or of the area they prefer). Covers ~1,800 US towns in
    all 50 states. Does all lookups, math and ranking; pass raw user inputs only, and omit
    any amount the user didn't state.

    Args:
        move_date: Target move date as YYYY-MM-DD.
        offers: Job offers to compare, each with city, annual salary and optional state code. Towns near each offer city are considered.
        salary: Annual salary in USD when there are no offers (one job, or remote work).
        work_city: City the user will work in or prefers to live near. Omit if remote with no preferred area, to rank everywhere.
        work_state: Two-letter state code of work_city, if known.
        radius_miles: How far from the work city to look for towns, in miles. Default 50.
        preferences: Lifestyle priorities the user mentioned, from: nightlife, outdoors, transit, food, weather.
        current_city: City the person lives in now. Omit if unknown (a long-distance move is assumed).
        bedrooms: Bedrooms wanted (0 for studio). Default 1.
        current_savings: Money already saved toward the move, in USD. Default 0.
        current_salary: Gross annual salary the person earns NOW, in USD (0 if not working now).
        current_rent: Monthly rent the person pays NOW, in USD (0 if living rent-free).
        monthly_bills: Recurring monthly bills other than rent (phone, insurance, subscriptions, car), in USD.
        monthly_debt_payments: Monthly debt payments (student loans, car loan, credit cards), in USD. Not the balance.
        monthly_spending: Other monthly spending (groceries, eating out, gas, fun), in USD.
        debt_balance: Total debt owed, in USD, only if the user gave a balance but no monthly payment.
    """
    finances = dict(current_salary=current_salary, current_rent=current_rent, monthly_bills=monthly_bills,
                    monthly_debt_payments=monthly_debt_payments, monthly_spending=monthly_spending,
                    debt_balance=debt_balance)
    prefs = [p for p in (preferences or []) if p in _LIFESTYLE_KEYS]

    # Jobs: (work place key or None if remote, salary, name the user gave)
    if offers:
        jobs = [(_resolve(o["city"], o.get("state")), o["salary"], o["city"]) for o in offers]
        unknown = [name for key, _, name in jobs if key is None]
        jobs = [j for j in jobs if j[0] is not None]
    elif salary is not None:
        key = _resolve(work_city, work_state) if work_city else None
        unknown = [work_city] if work_city and key is None else []
        jobs = [] if unknown else [(key, salary, work_city)]
    else:
        return {"error": "need either offers or a salary"}
    if not jobs:
        return {"error": f"no location data for: {', '.join(unknown)}"}

    best: dict[str, dict] = {}  # place key -> best-scoring option for that place
    for work_key, job_salary, _ in jobs:
        work_name = _PLACES[work_key]["name"] if work_key else None
        for key, place in _PLACES.items():
            miles = _miles_between(work_key, key) if work_key else None
            if miles is not None and miles > radius_miles:
                continue
            plan = compute_plan(job_salary, place["name"], place["state"], move_date,
                                current_city=current_city, bedrooms=bedrooms,
                                current_savings=current_savings, **finances)
            if "error" in plan:
                return plan

            budget = plan["monthly_budget"]
            rent_pct = round(budget["rent"] / budget["take_home"] * 100) if budget["take_home"] else 100
            parts = [(0.5, _affordability(rent_pct))]
            reasons = [f"Rent is {rent_pct}% of take-home pay"]
            if len(jobs) > 1:  # only worth saying which job when comparing several
                reasons.insert(0, f"Job in {work_name} at ${job_salary:,.0f}")
            if miles is not None:
                parts.append((0.2, _commute(miles, radius_miles)))
                if miles >= 1:
                    reasons.append(f"{miles:.0f} mi from {work_name} (straight line)")
            if prefs:
                est = _LIFESTYLE.get(key)
                scores: dict[str, int] = dict(zip(_LIFESTYLE_KEYS, est or (_NEUTRAL,) * 5))
                parts.append((0.3, sum(scores[p] for p in prefs) / len(prefs) / 5 * 100))
                if est:
                    reasons += [f"{p.capitalize()}: {scores[p]}/5 (estimate)" for p in prefs]
                else:
                    reasons.append(f"No {'/'.join(prefs)} data; scored as average")
            score = round(sum(w * x for w, x in parts) / sum(w for w, _ in parts))

            option = {
                "city": place["name"], "state": place["state"], "salary": job_salary,
                "work_city": work_name,
                "miles_from_work": round(miles, 1) if miles is not None else None,
                "score": score, "reasons": reasons, **plan,
            }
            if key not in best or score > best[key]["score"]:
                best[key] = option

    # Tie-break on lower monthly savings needed.
    ranked = sorted(best.values(), key=lambda o: (-o["score"], o["monthly_savings"]))
    top = [{"rank": i + 1, **o} for i, o in enumerate(ranked[:3])]
    if not top:
        return {"error": f"no towns within {radius_miles:g} miles"}
    return {"options": top, "skipped": unknown}


TOOLS = [get_rent, calc_take_home, get_move_costs, compute_plan, compare_options]
