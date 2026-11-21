"""
The data format between the agent (Gemini lane) and the UI.

The UI calls one function:

    respond(messages: list[dict]) -> dict

`messages` is the full chat so far: [{"role": "user" | "assistant", "content": str}, ...]

REQUIRED fields (this is the backend's format):

    {
        "monthly_savings": 950,
        "total_needed": 11400,
        "deadline": "2027-06-01",            # ISO date
        "move_in_costs": {                    # any keys; known ones get nice labels in the UI
            "first_month": 2400,
            "deposit": 2400,
            "movers": 1200,
            "furniture": 1500,
        },
        "monthly_budget": {"rent": 2400, "take_home": 5100},
        "warnings": ["Rent is 47% of take-home pay"],
        "follow_up_question": None,          # a string here means "ask the user this";
                                             # the other fields can then be left out
    }

OPTIONAL fields. The UI shows more if these are present:

    "message": "Plain-English summary, or what changed after a 'what if'.",
    "months_to_save": 7,                     # otherwise computed from today to deadline
    "monthly_budget": {..., "bills": 450, "debt_payment": 230},
    "move_in_costs": {..., "paycheck_gap": 1600, "broker_fee": 4300},
    "warnings": [{"level": "error", "text": "..."}],   # a warning may also be a dict; level is
                                             # "error" (red), "warning" (amber, the default) or "info"
    "profile": {                             # what Gemini parsed; shown in "What we understood"
        "salary": 85000, "current_city": "Chicago, IL", "target_city": "Seattle, WA",
        "debt": 20000, "monthly_bills": 450, "current_savings": 1500, "roommate": True,
    },

Rule: every dollar figure comes from a tool, never made up by Gemini.
"""
