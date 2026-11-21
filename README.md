# Relocation Savings Planner — Project Overview

## What it is

An AI planner that tells you how much to save, and by when, to move to any US city. You describe your situation in plain English: your job and salary, where you live now, your debt, your bills, where you want to go and when. The app returns a month-by-month savings plan built on real cost data.

The problem: people moving for a first job, especially new grads, underestimate what a move costs. Rent is only part of it. Security deposits, movers, furniture, a higher tax bill and the weeks before the first paycheck catch people off guard. A financial advisor could plan this, but most new grads don't have one.

## Who it's for and the track fit

The target user is a student or new grad about to relocate for work, with no money-savvy advisor to lean on. The project is entered in the MT-haCks **Fintech** track and uses Gemini, the sponsor's model.

| Track goal | How we meet it |
| --- | --- |
| Smarter money management | A savings target, a timeline and warnings built from real costs, debt and a deadline |
| Accessibility | Anyone can type their situation in plain English and get a real plan, no finance background needed |
| Simplify transactions | Not a focus |

## How it works

The user types one paragraph and gets back a full plan, then can ask "what if" questions.

1. **The user describes their situation.** Example: "I'm graduating in May, making 85k in Chicago, $20k in student loans, want to move to Seattle by September, open to a roommate."
2. **Gemini parses it** into structured fields: salary, current city, target city, debt, bills, deadline, preferences. If something is missing, it asks a follow-up question.
3. **Gemini calls our tools** to get real numbers: rent in the target city, take-home pay after taxes, moving costs.
4. **Gemini builds the plan:**
   - One number up top: "You need $X by \[date\], which means $Y/month starting now."
   - Move-in costs: first month's rent, security deposit, movers, furniture, the gap before the first paycheck.
   - Warnings, such as rent above 30% of take-home pay, or (NYC) a salary below the 40x-rent rule many landlords use.
5. **The user asks follow-ups** (stretch goal), such as "What if I move in December?" or "What if I skip the roommate?" Gemini reruns the tools and explains what changed.

The rule throughout: Gemini reasons, our tools supply the numbers. Gemini never makes up a dollar figure.

## Architecture

&#91;embedded content: architecture · UI, Gemini agent, 3 tools\]

Gemini uses function calling: it reads each Python function's name, type hints and docstring, decides which to call, and reasons over what comes back. Stack: Python, the `google-genai` SDK and Streamlit.

| Tool | Returns | Data source |
| --- | --- | --- |
| `get_rent(city, bedrooms)` | Monthly rent | Hand-built JSON of \~25 major metros from HUD Fair Market Rents. Other cities fall back to Gemini search grounding, labeled "estimate" in the UI. |
| `calc_take_home(salary, state, city)` | Monthly take-home pay | Federal brackets + one flat rate per state; NYC city tax handled exactly |
| `get_move_costs(from, to)` | One-time move cost | Simple estimate by distance |

This setup lets us pitch nationwide coverage honestly: every number traces back to a source.

## Scope for today

We have six hours (11:00 AM to 5:00 PM), so the scope is cut hard.

**In**

- Plain-English input, Gemini parsing, follow-up questions for missing info
- Three tools: rent, take-home pay, moving costs
- A savings plan with one headline number, move-in costs and warnings
- A Streamlit UI with the plan and one chart

**Stretch (only if the core works by 3:00 PM)**

- "What if" follow-ups
- Interest-free savings toggle: the plan assumes no interest income and flags interest-bearing debt separately
- Plaid Sandbox "connect your bank" to auto-fill bills

**Out**

- Login, database, real bank data
- Exact taxes for every city (federal brackets + one flat rate per state, NYC handled exactly)
- Scraping live listings

## Team roles and schedule

Each lane can work in parallel until the 1:30 checkpoint. With two people, merge Data + tools into the Gemini lane.

| Lane | Owns | Owner |
| --- | --- | --- |
| Gemini / agent | System prompt, function calling, parsing, plan generation |  |
| Data + tools | Metro rent JSON, take-home tax calc, move-cost estimate |  |
| UI | Streamlit page: input box, plan display, chart (mock data first) |  |
| Integration + demo | Wiring lanes together, backup video, submission, pitch |  |

| Time | Goal |
| --- | --- |
| 11:00–11:30 | Assign lanes, set up repo, each person gets a Gemini key working |
| 11:30–1:30 | Build lanes in parallel |
| 1:30–2:00 | **Checkpoint:** Gemini calls one tool end to end. If not, everyone helps fix it. |
| 2:00–3:30 | Wire it together: paragraph in, plan out |
| 3:30–4:15 | Polish: headline number, chart, 40x rent warning; stretch goals if time |
| 4:15–5:00 | **Stop coding.** Record backup demo video, write submission, rehearse pitch |

## Getting started

Get Gemini calling one fake tool before anything else. The whole app depends on it.

1. Get a free Gemini API key from Google AI Studio. Each teammate makes their own, since keys are rate-limited.
2. Set up the project:

```bash
mkdir relocate-ai && cd relocate-ai
python -m venv venv && source venv/bin/activate
pip install google-genai streamlit python-dotenv
```

3. Put the key in `.env` as `GEMINI_API_KEY=...` and add `.env` to `.gitignore` before the first commit.
4. Run this test. If the answer mentions $2,400, function calling works.

```python
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_rent(city: str, bedrooms: int) -> dict:
    """Returns average monthly rent for a city."""
    return {"city": city, "bedrooms": bedrooms, "rent": 2400}  # hardcoded for now

resp = client.models.generate_content(
    model="gemini-2.5-flash",  # check AI Studio for the current flash model name
    contents="What would a 1-bedroom cost me in Seattle?",
    config=types.GenerateContentConfig(tools=[get_rent]),
)
print(resp.text)
```

5. Check the MT-haCks Track Packet's Fintech data list before building the rent JSON by hand. It may already have the data.

## Demo and pitch

**Pitch line:** We make relocation planning accessible to anyone, and help new grads manage money smarter before their biggest financial move.

**Demo flow (under 3 minutes)**

1. The problem in one sentence: a new grad got a job in another city and has no idea what to save.
2. Paste one messy paragraph about their life into the app.
3. Show Gemini asking a follow-up question for a missing detail.
4. Show the plan: the headline savings number, the move-in cost breakdown, and a warning.
5. If built: ask "What if I get a roommate?" and show the number drop.
6. Close on the architecture: Gemini as an agent calling real-data tools, not a chatbot guessing numbers.

**Demo safety**

- Cache responses for the demo inputs so a rate-limit error can't break it live.
- Have the backup video ready to play.
