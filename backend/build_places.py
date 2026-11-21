"""Build backend/data/places.json from US Census data (no API key needed).

Sources (public domain, U.S. Census Bureau):
  - Rent: ACS 2020-2024 5-year, table B25031 "Median Gross Rent by Bedrooms" (place level)
  - New-lease adjustment: ACS table B25113 "Median Gross Rent by Year Householder Moved Into
    Unit". Rent by bedrooms is multiplied by (median rent of households that moved in 2023 or
    later / median rent of all renters), clamped to [1.0, 2.0], so the numbers reflect what
    someone signing a lease now pays rather than long-time tenants.
  - Population: ACS 2020-2024 5-year, table B01003 "Total Population"
  - Coordinates: 2024 Census Gazetteer, places (internal point lat/lon)

Keeps, for each state + DC: the 15 most populous places with a 1-bedroom rent estimate,
plus every place over 25,000 people. "Places" include cities, towns and CDPs.

Usage (from repo root):
  1) Download into an empty folder:
       https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25031.dat
       https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b01003.dat
       https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25113.dat
       https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip (unzip it)
  2) python -I backend/build_places.py <download folder>
"""

import csv
import json
import re
import sys
from pathlib import Path

PER_STATE = 15
FACTOR_MIN, FACTOR_MAX = 1.0, 2.0
# Drop estimates whose 90% margin of error exceeds 25% of the estimate (coefficient of
# variation above ~15%). Small towns with few apartments otherwise produce rents like $300.
MAX_MOE_RATIO = 0.25
# Drop places whose 1BR median is under 60% of the 2BR median: a sign the 1BR stock is mostly
# subsidized or senior housing, which a new mover can't rent.
MIN_1BR_TO_2BR = 0.6
# States with fewer than MIN_PER_STATE reliable places (e.g. RI, where most "places" are tiny
# CDPs) are topped up with places passing a looser margin-of-error limit, flagged "lower".
MIN_PER_STATE = 10
LOOSE_MOE_RATIO = 0.5
BIG_PLACE = 25_000
OUT = Path(__file__).parent / "data" / "places.json"
# Every US place (no rent needed), so towns without rent data can still be located and matched
# to the nearest place that has it. Rows: [name, state, lat, lon, population].
COORDS_OUT = Path(__file__).parent / "data" / "place_coords.json"

# ACS "no estimate" sentinels are large negative numbers.
def _num(v: str) -> int | None:
    try:
        n = int(v)
    except ValueError:
        return None
    return n if n >= 0 else None


_SUFFIX = re.compile(
    r"\s+(city and borough|consolidated government|metropolitan government|metro government|"
    r"unified government|urban county|city|town|village|borough|municipality|CDP|plantation|"
    r"township|charter township|corporation|comunidad|zona urbana)$",
    re.IGNORECASE,
)


def clean_name(raw: str) -> str:
    name = re.sub(r"\s*\(balance\)$", "", raw.strip())
    # Strip ONE legal suffix: "Jersey City city" -> "Jersey City",
    # "Nashville-Davidson metropolitan government" -> "Nashville-Davidson"
    name = _SUFFIX.sub("", name, count=1)
    # Massachusetts "town cities": "Braintree Town city" -> "Braintree"
    if raw.strip().endswith(" Town city"):
        name = name.removesuffix(" Town")
    # "Nashville-Davidson" -> "Nashville", "Louisville/Jefferson County" -> "Louisville"
    if re.search(r"(Davidson|Jefferson County|Marion County|Athens-Clarke|Augusta-Richmond|Lexington-Fayette)", name):
        name = re.split(r"[-/]", name)[0]
    return {"Boise City": "Boise"}.get(name.strip(), name.strip())  # Census's legal name


def _table(folder: Path, table: str) -> Path:
    full = folder / f"acsdt5y2024-{table}.dat"
    return full if full.exists() else folder / f"{table}.dat"


def main(folder: Path) -> None:
    factor: dict[str, float] = {}
    with open(_table(folder, "b25113"), newline="") as f:
        for row in csv.DictReader(f, delimiter="|"):
            if not row["GEO_ID"].startswith("1600000US"):
                continue
            total, recent = _num(row["B25113_E001"]), _num(row["B25113_E002"])
            if total and recent:
                factor[row["GEO_ID"][9:]] = round(min(FACTOR_MAX, max(FACTOR_MIN, recent / total)), 3)

    rent: dict[str, dict[str, dict[str, int]]] = {"high": {}, "lower": {}}
    with open(_table(folder, "b25031"), newline="") as f:
        for row in csv.DictReader(f, delimiter="|"):
            geo = row["GEO_ID"]
            if not geo.startswith("1600000US"):
                continue
            for level, max_ratio in (("high", MAX_MOE_RATIO), ("lower", LOOSE_MOE_RATIO)):
                beds = {}
                # Studio through 4BR. The "5 or more" group is skipped: it mixes very different
                # homes and often comes out cheaper than 4BR (e.g. Boston), which isn't usable.
                for k, i in (("0", 2), ("1", 3), ("2", 4), ("3", 5), ("4", 6)):
                    est, moe = _num(row.get(f"B25031_E00{i}", "")), _num(row.get(f"B25031_M00{i}", ""))
                    beds[k] = est if est and moe is not None and moe <= max_ratio * est else None
                if beds["1"] is not None and not (beds["2"] and beds["1"] < MIN_1BR_TO_2BR * beds["2"]):
                    k = factor.get(geo[9:], 1.0)
                    rent[level][geo[9:]] = {b: round(v * k) for b, v in beds.items() if v is not None}
                    break  # passed the strict filter: don't also file it as "lower"

    pop: dict[str, int] = {}
    with open(_table(folder, "b01003"), newline="") as f:
        for row in csv.DictReader(f, delimiter="|"):
            if row["GEO_ID"].startswith("1600000US") and (n := _num(row["B01003_E001"])) is not None:
                pop[row["GEO_ID"][9:]] = n

    by_state: dict[str, list[dict]] = {}
    coords: list[list] = []
    with open(folder / "2024_Gaz_place_national.txt", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        header = [h.strip() for h in next(reader)]
        for cols in reader:
            row = dict(zip(header, (c.strip() for c in cols)))
            geoid, state = row["GEOID"], row["USPS"]
            if state != "PR":
                coords.append([clean_name(row["NAME"]), state, round(float(row["INTPTLAT"]), 3),
                               round(float(row["INTPTLONG"]), 3), pop.get(geoid, 0)])
            level = "high" if geoid in rent["high"] else "lower" if geoid in rent["lower"] else None
            if state == "PR" or level is None or geoid not in pop:
                continue
            by_state.setdefault(state, []).append({
                "name": clean_name(row["NAME"]),
                "state": state,
                "lat": round(float(row["INTPTLAT"]), 4),
                "lon": round(float(row["INTPTLONG"]), 4),
                "population": pop[geoid],
                "rent": rent[level][geoid],
                "new_lease_factor": factor.get(geoid, 1.0),
                "reliability": level,
                "geoid": geoid,
            })

    places = []
    for state, rows in sorted(by_state.items()):
        rows.sort(key=lambda r: -r["population"])
        seen: set[str] = set()  # same cleaned name twice in a state (e.g. city + CDP): keep larger
        rows = [r for r in rows if not (r["name"].lower() in seen or seen.add(r["name"].lower()))]
        good = [r for r in rows if r["reliability"] == "high"]
        keep = [r for i, r in enumerate(good) if i < PER_STATE or r["population"] >= BIG_PLACE]
        if len(keep) < MIN_PER_STATE:
            keep += [r for r in rows if r["reliability"] == "lower"][: MIN_PER_STATE - len(keep)]
        places += keep

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "source": "U.S. Census Bureau: ACS 2020-2024 5-year B25031 (median gross rent by bedrooms, "
                  "2024 dollars, includes utilities), adjusted to new-lease levels with B25113 "
                  "(rent of households moved in 2023 or later vs all renters); B01003 (population); "
                  "2024 Gazetteer (coordinates)",
        "places": places,
    }, separators=(",", ":")) + "\n")
    COORDS_OUT.write_text(json.dumps(coords, separators=(",", ":")) + "\n")
    print(f"Wrote {len(coords)} place coordinates to {COORDS_OUT}")
    counts = {s: sum(p["state"] == s for p in places) for s in by_state}
    print(f"Wrote {len(places)} places in {len(counts)} states to {OUT}")
    print("Fewest per state:", sorted(counts.items(), key=lambda kv: kv[1])[:5])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
