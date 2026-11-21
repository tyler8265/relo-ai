# reloai: Relocation Savings Planner

**Live app: https://relocate-ai-six.vercel.app**

Tell reloai about your move in plain English: the job offer, where you live now, what you earn and spend today, and when you want to go. It tells you how much to save, and by when, using Census rent data for the town you're moving to. That includes the costs people usually forget: the security deposit, movers, furniture, living expenses until the first paycheck, and an emergency buffer.

It can also compare job offers, suggest the best towns to live in near where you'll work, and show how roommates change the plan.

Built for the MT-haCks Fintech track.

## What it does

- **A savings plan from one message.** For example: "I have an 85k offer in Boston, I live in Phoenix, moving September 2027." The reply is the total you need, the monthly amount to save starting now, and an itemized list of move-in costs.
- **Asks only for what's missing.** The salary, destination and move date are required; everything else is optional.
- **Checks the plan against your real budget.** It compares your take-home pay before and after the move with your rent, bills, debt payments and spending, and warns you when the monthly target is more than you can save today.
- **Fills gaps with typical spending.** If you don't say what you spend, it uses typical everyday spending for your state, and says so.
- **Ranks where to live.** Ask for a suburb, "somewhere near Seattle", or compare offers in different cities, and it ranks every town within 50 miles of the job. You get the top 3, each with its own plan and a score breakdown that explains it.
- **Plays out "what ifs".** Add roommates (up to 3), live alone, or change the move date, and the plan updates.
- **Raises warnings.** For example: rent over 30% of take-home pay, a salary below NYC's 40x-rent rule, or a town without its own rent data.

## How it works

1. **The model reads.** An AI agent (Groq, model `openai/gpt-oss-120b`) pulls the details out of the conversation: salary, cities, move date, current finances, roommates and preferences. It then picks a planning tool, or asks one follow-up question if something required is missing.
2. **Python calculates.** The tools look up rent, calculate taxes and take-home pay, add up move-in costs and the cushion, check both budgets, and rank towns.
3. **The answer is Python's output.** The model never writes a dollar figure, does arithmetic or ranks towns. When a tool succeeds, the plan you see is that tool's result, unchanged.

**How towns are ranked.** Each town gets a score from 0 to 100:

| Factor | Weight | Full points | No points |
| --- | --- | --- | --- |
| Affordability | 50% | Rent at 30% of take-home pay or less | Rent at 60% or more |
| Commute | 20% | In the work city | At the edge of the radius |
| Lifestyle | 30% | Your preferences (nightlife, outdoors, transit, food, weather) rated 5/5 | Rated 0/5 |

A factor that doesn't apply, such as commute for remote work, is left out, and the other weights scale up to compensate.

## Where the numbers come from

| Number | Source |
| --- | --- |
| Rent by bedrooms | U.S. Census Bureau, American Community Survey (ACS) 2020–2024 5-year estimates, table B25031: median gross rent (utilities included) for studios through 4-bedrooms, in 2024 dollars |
| New-lease adjustment | ACS table B25113. Each town's rent is multiplied by (median rent of households that moved in 2023 or later ÷ median rent of all renters), between 1.0× and 2.0×, so it reflects what a new lease costs rather than long-time tenants' rents. |
| Towns, population, locations | ACS table B01003 and the 2024 Census Gazetteer. Rent data covers 1,791 towns (the 15 largest in each state plus every town over 25,000 people; DC is one city), and coordinates cover all ~32,000 US places. A town without rent data uses the nearest one that has it, within 100 miles. |
| Data quality | Rent estimates are dropped when their margin of error is over 25% of the estimate, when a 1-bedroom is under 60% of the 2-bedroom (usually subsidized housing), and for the "5 or more bedrooms" group |
| Typical spending | U.S. Bureau of Economic Analysis, per-person spending by state, 2024 (table SAPCE2): groceries, dining out, clothing, gas, transportation and recreation. That's about $1,300/month nationally. Used only when you don't give your own. |
| Taxes | Approximate: federal brackets and standard deduction, Social Security and Medicare, a flat rate per state, approximate NYC city tax |
| Movers, furniture | Flat estimates: $1,200 for a long-distance move ($500 local), $1,500 for furniture |
| Cushion | Expenses before the first paycheck: one month of bills, debt payments and spending. Emergency buffer: one month of take-home pay. |
| Lifestyle scores | Hand-assigned estimates for about 55 places, labeled "(estimate)". Other towns score average. |

All Census and BEA data is public domain.

## Architecture

```
Browser (frontend/static: index.html, app.js, styles.css)
   │  POST /api/respond {"messages": [...the whole chat...]}
   ▼
api/index.py (FastAPI)       on Vercel; also serves the static files
frontend/server.py           the same API for local use, standard library only
   │
   ▼
frontend/backend_bridge.py   picks the answer source, in order:
   1. backend/demo_cache.json   saved answers for the demo inputs (instant, no Groq)
   2. backend/agent.py          the live Groq agent: build_plan(messages)
   3. frontend/mock_agent.py    placeholder numbers, labeled, if the agent can't run
   │
   ▼
backend/tools.py             rent, taxes, costs, budgets, ranking (all the math)
backend/data/*.json          Census and BEA data
```

If the main Groq model is rate-limited, `agent.py` waits briefly and retries, then tries the fallback models in `GROQ_FALLBACK_MODEL`.

## Project layout

| Path | What it is |
| --- | --- |
| `frontend/static/` | The web app: chat, boarding-pass plan, cost breakdown, ranked options |
| `frontend/adapter.py` | Converts the planner's response into the shape the UI renders |
| `frontend/backend_bridge.py` | Chooses demo cache, live agent or mock |
| `frontend/server.py` | Local web server for the app |
| `api/index.py` | The Vercel entry point (FastAPI) |
| `backend/agent.py` | The Groq tool-calling loop. It's the only code that talks to the LLM. |
| `backend/tools.py` | `get_rent`, `calc_take_home`, `get_move_costs`, `compute_plan`, `compare_options` |
| `backend/data/` | `places.json` (rent and towns), `place_coords.json` (all US places), `spending_by_state.json` |
| `backend/build_places.py`, `backend/build_spending.py` | Rebuild the data files from Census and BEA downloads; links are in each script's docstring |
| `backend/build_demo_cache.py` | Saves live answers for the demo inputs to `demo_cache.json` |
| `backend/main.py` | A standalone FastAPI API, `POST /plan {"situation": "..."}`, with a sample-plan fallback |

## Run it locally

You need Python 3.11+ and a free Groq API key from https://console.groq.com.

```bash
python3 -m venv backend/venv
backend/venv/bin/pip install -r requirements.txt
```

Create `backend/.env` (it's git-ignored):

```
GROQ_API_KEY=your-key
GROQ_MODEL=openai/gpt-oss-120b
```

Start the app from the repo root, then open http://localhost:8000:

```bash
backend/venv/bin/python frontend/server.py
```

The startup line tells you whether the app is using the live agent, only the demo cache, or the mock. `RELO_MOCK=1` forces the mock, and `PORT=8001` changes the port. The server doesn't reload on its own, so restart it after changing Python files or `.env`.

Other useful commands:

| Command | What it does |
| --- | --- |
| `backend/venv/bin/python backend/agent.py` | Runs sample situations through the agent |
| `backend/venv/bin/python backend/build_demo_cache.py` | Refreshes the demo answers. The monthly figures depend on today's date, so run it before a demo. |
| `cd backend && venv/bin/uvicorn main:app --reload` | Runs the standalone `/plan` API; try it at http://localhost:8000/docs |

`http://localhost:8000/#sample` loads a saved response with three ranked towns.

## Deploy

The app runs on Vercel as one Python function (`api/index.py`) that serves the API and the static files. `vercel.json` bundles `backend/` and `frontend/` into the function, and `.vercelignore` keeps `.env` and `venv/` from being uploaded.

```bash
npx vercel login
npx vercel env add GROQ_API_KEY production
npx vercel env add GROQ_MODEL production
npx vercel deploy --prod
```

Vercel doesn't read `backend/.env`; it uses its own environment variables. Redeploy after every change.

## API

`POST /api/respond` with the whole chat:

```json
{ "messages": [{ "role": "user", "content": "I have an 85k offer in Boston, moving September 2027 from Phoenix." }] }
```

You get back either a question, `{"type": "question", "message": "..."}`, or a plan:

```json
{
  "type": "plan",
  "source": "live",
  "message": "You need **$14,889 by September 2027**. That means saving **$1,489/month** starting now.",
  "plan": {
    "profile": { "current_city": "Phoenix, AZ", "target_city": "Boston, MA", "salary": 85000, "roommates": 0 },
    "target_total": 14889,
    "monthly_savings": 1489,
    "deadline": "2027-09-01",
    "move_in_costs": [{ "label": "First month's rent", "amount": 2642 }, "..."],
    "monthly_budget": { "take_home": 5390, "rent": 2642, "spending": 1515, "leftover": 1233 },
    "warnings": [{ "level": "warning", "text": "Rent is 49% of take-home pay (guideline: 30%)" }]
  },
  "options": []
}
```

`source` is `cache`, `live` or `mock`. When towns are compared, `options` holds the top 3. Each has `rank`, `city`, `score`, `score_breakdown` (each factor's points, weight and reason), `reasons` and its own `plan`.

## Limits

- **Groq's free tier:** it allows about 4–5 plans a minute and 200,000 tokens a day. Past that, the app shows the labeled mock plan. The demo inputs always work, because they come from the cache.
- **Rent is in 2024 dollars**, not projected to your move date.
- **Distances are straight lines**, not drive times. Taxes, movers and furniture are estimates.
