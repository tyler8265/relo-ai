# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Custom HTML/CSS/JS (no framework, no build step), served by a small Python standard-library server
(`frontend/server.py`) that calls the agent's `respond(messages)` and the frontend adapter. Chosen by the
user on 2026-11-21. The earlier Streamlit app (`frontend/app.py`) stays as a fallback.

## Users

Students and new grads about to relocate to a US city for a first job, with no financial advisor. They
know their salary, debt, bills, current city, target city and rough move date, but not what the move
will actually cost or how much to set aside each month.

The primary viewers today are hackathon judges (MT-haCks, Fintech track) watching a live, under-3-minute
demo on a laptop that is projected or screen-shared.

## Product Purpose

The user describes their situation in one plain-English paragraph. A Gemini agent parses it, asks a
follow-up question when something is missing, calls data tools (rent, take-home pay, moving costs), and
returns a savings plan: one headline number ("$X by [date], $Y/month starting now"), itemized move-in
costs, and warnings. Users can then ask "what if" follow-ups (roommate, a different month) and see what changed.

Success: a new grad leaves knowing one number to save per month, and judges see that it is accessible
(plain English in, real plan out) and trustworthy.

## Positioning

Gemini reasons; tools supply the numbers. Every dollar figure traces to a source (HUD Fair Market Rents,
federal and state tax rules, a distance-based move estimate). Figures from search grounding are labeled
"estimate". The product never invents a dollar amount.

## Operating Context

- One conversational input, then a plan; follow-ups refine the plan in place.
- Demo flow: paste a messy paragraph → show a follow-up question → show the plan (headline number, cost
  breakdown, a warning) → ask "What if I get a roommate?" and show the number drop.
- Data contract: `contract.py`. Backend response fields: monthly_savings, total_needed, deadline,
  move_in_costs (dict), monthly_budget (rent, take_home, optional bills and debt_payment), warnings (strings),
  follow_up_question, plus optional message, months_to_save and profile.

## Capabilities and Constraints

- In scope: plain-English input, follow-up questions, rent, take-home and moving-cost tools, the plan with
  a headline number, move-in costs and warnings, one chart; stretch: "what if" follow-ups.
- Out of scope: login, database, real bank data, scraping live listings.
- The UI must work with only the required backend fields; optional fields add detail.
- The agent can be rate-limited; the UI must survive errors without breaking the demo.
- Until `agent.py` exists, a mock agent (`frontend/mock_agent.py`) supplies placeholder numbers.

## Brand Commitments

Name: Relo AI ("Relocation Savings Planner"), wordmark set lowercase as "reloai". Pitch line: "We make
relocation planning accessible to anyone, and help new grads manage money smarter before their biggest
financial move."

Logo (supplied by the user 2026-11-21, binding): a rounded-square tile with a left-to-right gradient from
deep blue (~#0A4BAA) to violet-pink (~#C66BE2), holding two overlapping circles, a larger light teal
(~#7FD3C9) and a smaller dark teal (~#00989F) in front. Wordmark "reloai" in a geometric bold sans
(Poppins Bold) in orange (~#FF924F). The user asked for the logo's colours to be the app's colour scheme.
Recreated as SVG in frontend/static/logo.svg; replace with the original file when available.

## Evidence on Hand

No real users, testimonials, metrics or partner logos exist. Do not fabricate any. Mock data is placeholder
and must be visibly labeled as such while it is in use.

## Product Principles

1. One number first. Everything else explains or adjusts it.
2. Show your sources. Every figure can be traced, and estimates say so.
3. Plain English in, plain English out. No finance jargon without a plain explanation.
4. Honest about bad news. Warnings (rent over 30% of pay, the NYC 40x rule, an unrealistic savings rate) are
   shown clearly, not softened.
5. Legible from across a room. The demo is projected; key figures must read instantly.
