# Relocation Savings Planner

## What it is

An AI planner that tells you how much to save, and by when, to move for a job anywhere in the US. You describe your situation in plain English: the job offer, where you live now, what you earn and spend today, your debt, and when you want to move. The app returns a savings plan built on Census rent data, including the cushion most people forget. It can also compare job offers and recommend the best towns to live in near where you'll work.

The problem: people moving for a first job, especially new grads, underestimate what a move costs. Rent is only part of it. Security deposits, movers, furniture, the weeks before the first paycheck and the lack of an emergency fund catch people off guard. A financial advisor could plan this, but most new grads don't have one.

## Who it's for and the track fit

The target user is a student or new grad about to relocate for work, with no money-savvy advisor to lean on. The project is entered in the MT-haCks **Fintech** track.

| Track goal | How we meet it |
| --- | --- |
| Smarter money management | A savings target and timeline built from Census rents, real taxes and the user's own bills, debt and spending, with a check that the target fits their current budget |
| Accessibility | Anyone can type their situation in plain English and get a real plan, no finance background needed |
| Simplify transactions | Not a focus |

We planned to use Gemini, the sponsor's model, but our Gemini project had no prepaid credits. The agent runs on Groq instead. Only `backend/agent.py` talks to the model, so switching back is a one-file change.

## How it works

1. **The user describes their situation.** Example: "I make 60k right now in Chicago and pay 1,400 rent. My bills are about 300 a month, I pay 250 a month on student loans, and I spend around 900 on food and fun. I got an 85k offer in Seattle and want to move by September 2027. I have 1,000 saved."
2. **The model extracts the details** (new salary, cities, move date, current income, rent, bills, debt payments, spending, preferences) and picks a tool. If the salary, target city or move date is missing, it asks one follow-up question instead.
3. **Python does every calculation.** It looks up rent, computes take-home pay after taxes, adds move-in costs and the cushion, and checks the plan against the user's current budget.
4. **The user gets a plan:**
   - The headline: you need **$13,842 by September 2027**, which means **$1,285/month** starting now.
   - Move-in costs: first month's rent, deposit, movers, furniture, **expenses before the first paycheck** (one month of bills, debt payments and spending, since the first check often takes 2–4 weeks) and an **emergency buffer** (one month of new take-home pay).
   - Their budget after the move, and how much they have left over today.
   - Warnings, such as: rent is 35% of take-home pay; saving $1,285/month is more than the $1,152/month you have left over now, so at that rate you'd be ready by November 2027; or (NYC) your salary is below the 40x-rent rule many landlords use.
5. **Comparing options.** With several offers, a preferred area or lifestyle preferences ("I love hiking", "good nightlife"), the app ranks every town within 50 miles of each job and returns the top 3, each with its own plan and the reasons for its rank.

**The rule throughout: the model reasons, Python supplies the numbers.** The model never makes up a dollar figure, does arithmetic or ranks cities. When a planning tool succeeds, the response is Python's output, unchanged.

## Architecture

```
React UI (localhost:5173)
   │  POST /plan {"situation": "..."}
   ▼
FastAPI (backend/main.py)
   │  demo cache hit? → saved response
   │  otherwise build_plan(situation); on any error → sample plan with a warning
   ▼
Groq agent (backend/agent.py)
   │  tool-calling loop: model picks a tool, Python runs it, result goes back
   ▼
Tools (backend/tools.py) ── data/places.json (Census rents, ~1,800 US towns)
```

Stack: Python, FastAPI, the `groq` SDK (model `openai/gpt-oss-120b`, OpenAI-style tool calling) and a React frontend. `agent.py` builds each tool's schema from the Python function's name, type hints and docstring.

| Tool | Returns |
| --- | --- |
| `get_rent(city, bedrooms, state)` | Monthly rent for a new lease |
| `calc_take_home(salary, state, city)` | Monthly take-home pay after federal, FICA, state and NYC city tax |
| `get_move_costs(from_city, to_city)` | One-time mover cost |
| `compute_plan(...)` | One city's full plan: costs, cushion, both budgets, warnings |
| `compare_options(...)` | The top 3 places to live across offers and nearby towns, each with a plan, score and reasons |

**Ranking.** Each candidate town gets a score from 0 to 100. Affordability counts for 50% (rent as a share of take-home pay), commute for 20% (distance from the job) and lifestyle preferences for 30%. When a part doesn't apply, the other weights are scaled up.

## Where the numbers come from

| Number | Source |
| --- | --- |
| Rent by bedrooms | U.S. Census Bureau, ACS 2020–2024 5-year estimates, table B25031 (median gross rent by bedrooms, utilities included), for ~1,800 places with at least 10 per state (DC is one city) |
| New-lease adjustment | ACS table B25113: rent is scaled by what households that moved in 2023 or later pay versus all renters. Long-time tenants pull the plain median down; NYC rises 40%, Seattle about 6%. |
| Town locations and population | 2024 Census Gazetteer and ACS table B01003 |
| Data quality | Rent estimates with a margin of error over 25% are dropped, as are towns where the 1-bedroom rent is under 60% of the 2-bedroom (a sign of mostly subsidized units) |
| Taxes | Approximate: federal brackets, FICA, a flat rate per state, approximate NYC city tax |
| Movers and furniture | Flat estimates: $1,200 for a long-distance move ($500 local) and $1,500 for furniture |
| Lifestyle scores | Hand-assigned estimates for about 55 places, labeled "(estimate)". Other towns score average and say "no data". |
| User's finances | Whatever the user types. Missing amounts count as $0, and a warning says so. |

`backend/build_places.py` rebuilds `data/places.json` from the free Census bulk files; the download links are in its docstring.

## Running it

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install fastapi uvicorn groq python-dotenv
```

Create `backend/.env` (it's already in `.gitignore`):

```
GROQ_API_KEY=your-key-from-console.groq.com
GROQ_MODEL=openai/gpt-oss-120b
```

Then:

| Command | What it does |
| --- | --- |
| `uvicorn main:app --reload` | Starts the API on http://localhost:8000. Test `POST /plan` at http://localhost:8000/docs. |
| `python agent.py` | Runs sample situations through the agent and prints the plans |
| `python build_demo_cache.py` | Saves the 3 demo inputs' responses to `demo_cache.json`. Rerun it on demo day, since the monthly figures depend on today's date. |

The API contract (every field of the `/plan` response) is documented in [CLAUDE.md](CLAUDE.md#api-contract).

## Scope

**Done**

- Plain-English input, follow-up questions for missing details
- A savings plan with move-in costs, expenses before the first paycheck, and an emergency buffer
- The user's current income, rent, bills, debt payments and spending, with a check that the savings target fits their budget
- Census rents for ~1,800 towns in all 50 states and DC
- Comparing job offers and ranking towns within 50 miles of a job, with lifestyle preferences
- A demo cache and a sample-plan fallback, so a rate limit or outage can't break the demo

**Stretch**

- "What if" follow-ups ("What if I move in December?", "What if I get a roommate?")
- Turning a debt balance into a monthly payment (today the app asks for the payment instead of guessing one)
- Distance-based mover costs and drive-time commutes
- Plaid Sandbox "connect your bank" to fill in bills and spending

**Out**

- Login, database, real bank data
- Exact taxes for every state and city
- Scraping live listings

**Known limits**

- **Groq's free tier allows 8,000 tokens a minute.** That's roughly 4 or 5 plans a minute; past that, the API returns the sample plan with a "sample numbers" warning.
- **Rent figures are in 2024 dollars**, not projected to the move date.
- **Distances are straight lines**, not drive times.

## Demo and pitch

**Pitch line:** We make relocation planning accessible to anyone, and help new grads manage money smarter before their biggest financial move.

**Demo flow (under 3 minutes)**

1. The problem in one sentence: a new grad got a job in another city and has no idea what to save.
2. Paste one messy paragraph about their life into the app.
3. Show the app asking a follow-up question for a missing detail.
4. Show the plan: the headline number, the move-in costs including the cushion ("you think you need $6,700; you really need $13,800"), and the warning that the target is more than they can save today.
5. Compare two offers, or ask for the best towns near a job, and show the top 3 with their reasons.
6. Close on the architecture: an AI agent that calls tools backed by Census data, not a chatbot guessing numbers.

**Demo safety**

- Paste the demo inputs from `backend/build_demo_cache.py` exactly as written. They're served from `demo_cache.json`, so they're instant and don't use Groq.
- If Groq fails mid-demo, the API returns a sample plan instead of an error.
- Have the backup video ready to play.
