"""Example backend responses from the Gemini lane, in the format from contract.py."""
import json

# First sample: a single plan.
SAMPLE_RESPONSE = {
    "monthly_savings": 950,
    "total_needed": 11400,
    "deadline": "2027-06-01",
    "move_in_costs": {
        "first_month": 2400,
        "deposit": 2400,
        "movers": 1200,
        "furniture": 1500,
    },
    "monthly_budget": {"rent": 2400, "take_home": 5100},
    "warnings": ["Rent is 47% of take-home pay"],
    "follow_up_question": None,
}

# Second sample (2026-11-21): ranked city options, each with its own full plan.
SAMPLE_OPTIONS_RESPONSE = json.loads(r"""
{
  "monthly_savings": 1245,
  "total_needed": 9957,
  "deadline": "2027-07-01",
  "move_in_costs": {"first_month": 1360, "deposit": 1360, "movers": 1200, "furniture": 1500, "paycheck_gap": 0, "emergency_buffer": 4537},
  "monthly_budget": {"rent": 1360, "take_home": 4537, "bills": 0, "debt_payments": 0, "spending": 0, "leftover": 3177},
  "current_budget": null,
  "warnings": ["Your monthly bills, debt payments, spending weren't given, so they're counted as $0; add them to size the paycheck gap and budget accurately"],
  "follow_up_question": null,
  "options": [
    {
      "rank": 1, "city": "Boise", "state": "ID", "salary": 70000, "work_city": "Boise", "miles_from_work": 0, "score": 88,
      "reasons": ["Job in Boise at $70,000", "Rent is 30% of take-home pay", "No nightlife data; scored as average"],
      "monthly_savings": 1245, "total_needed": 9957, "deadline": "2027-07-01",
      "move_in_costs": {"first_month": 1360, "deposit": 1360, "movers": 1200, "furniture": 1500, "paycheck_gap": 0, "emergency_buffer": 4537},
      "monthly_budget": {"rent": 1360, "take_home": 4537, "bills": 0, "debt_payments": 0, "spending": 0, "leftover": 3177},
      "current_budget": null,
      "warnings": ["Your monthly bills, debt payments, spending weren't given, so they're counted as $0; add them to size the paycheck gap and budget accurately"],
      "follow_up_question": null
    },
    {
      "rank": 2, "city": "Denver", "state": "CO", "salary": 90000, "work_city": "Denver", "miles_from_work": 0, "score": 86,
      "reasons": ["Job in Denver at $90,000", "Rent is 31% of take-home pay", "Nightlife: 3/5 (estimate)"],
      "monthly_savings": 1490, "total_needed": 11918, "deadline": "2027-07-01",
      "move_in_costs": {"first_month": 1759, "deposit": 1759, "movers": 1200, "furniture": 1500, "paycheck_gap": 0, "emergency_buffer": 5700},
      "monthly_budget": {"rent": 1759, "take_home": 5700, "bills": 0, "debt_payments": 0, "spending": 0, "leftover": 3941},
      "current_budget": null,
      "warnings": ["Rent is 31% of take-home pay (guideline: 30%)", "Your monthly bills, debt payments, spending weren't given, so they're counted as $0; add them to size the paycheck gap and budget accurately"],
      "follow_up_question": null
    },
    {
      "rank": 3, "city": "Commerce City", "state": "CO", "salary": 90000, "work_city": "Denver", "miles_from_work": 9.5, "score": 84,
      "reasons": ["Job in Denver at $90,000", "Rent is 25% of take-home pay", "10 mi from Denver (straight line)", "No nightlife data; scored as average"],
      "monthly_savings": 1402, "total_needed": 11210, "deadline": "2027-07-01",
      "move_in_costs": {"first_month": 1405, "deposit": 1405, "movers": 1200, "furniture": 1500, "paycheck_gap": 0, "emergency_buffer": 5700},
      "monthly_budget": {"rent": 1405, "take_home": 5700, "bills": 0, "debt_payments": 0, "spending": 0, "leftover": 4295},
      "current_budget": null,
      "warnings": ["Your monthly bills, debt payments, spending weren't given, so they're counted as $0; add them to size the paycheck gap and budget accurately"],
      "follow_up_question": null
    }
  ]
}
""")

SAMPLES = {"basic": SAMPLE_RESPONSE, "options": SAMPLE_OPTIONS_RESPONSE}
