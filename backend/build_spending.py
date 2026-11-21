"""Build backend/data/spending_by_state.json: typical monthly everyday spending per person, by state.

Source (public domain): U.S. Bureau of Economic Analysis, "Per capita personal consumption
expenditures by state" (table SAPCE2), by state of residence.

Used when the user doesn't give their own monthly spending. Includes everyday categories a
person pays for themselves; leaves out housing and utilities (already in the Census rent),
health care (mostly paid by employers and insurers), financial services and insurance (mostly
imputed), and goods bought rarely (cars, furniture).

Usage (from repo root):
  1) Download and unzip into an empty folder: https://apps.bea.gov/regional/zip/SAPCE.zip
  2) python -I backend/build_spending.py <download folder>
"""

import csv
import json
import sys
from pathlib import Path

YEAR = "2024"
OUT = Path(__file__).parent / "data" / "spending_by_state.json"

# SAPCE2 line code -> label shown to users
CATEGORIES = {
    "9": "groceries",
    "19": "dining out",
    "10": "clothing",
    "11": "gas",
    "17": "transportation",
    "18": "recreation",
}

STATE_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "United States": "US",
}


def main(folder: Path) -> None:
    src = next(folder.glob("SAPCE2__ALL_AREAS_*.csv"))
    annual: dict[str, dict[str, float]] = {}
    with open(src, newline="", encoding="latin-1") as f:
        for row in csv.DictReader(f):
            code = STATE_CODES.get((row.get("GeoName") or "").strip().rstrip("*").strip())
            line = (row.get("LineCode") or "").strip()
            if code and line in CATEGORIES:
                try:
                    annual.setdefault(code, {})[CATEGORIES[line]] = float(row[YEAR])
                except (KeyError, ValueError):
                    pass

    states = {}
    for code, cats in sorted(annual.items()):
        if len(cats) != len(CATEGORIES):
            continue
        monthly = {k: round(v / 12) for k, v in cats.items()}
        states[code] = {"monthly": sum(monthly.values()), "categories": monthly}

    OUT.write_text(json.dumps({
        "source": f"U.S. Bureau of Economic Analysis, per capita personal consumption expenditures "
                  f"by state (SAPCE2), {YEAR}: {', '.join(CATEGORIES.values())}",
        "year": int(YEAR),
        "states": states,
    }, indent=1) + "\n")
    print(f"Wrote {len(states)} states to {OUT}")
    lo = min(states.items(), key=lambda kv: kv[1]["monthly"])
    hi = max(states.items(), key=lambda kv: kv[1]["monthly"])
    print(f"US {states['US']['monthly']}/mo, lowest {lo[0]} {lo[1]['monthly']}, highest {hi[0]} {hi[1]['monthly']}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
