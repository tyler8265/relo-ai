## Scope

The Relo AI app screen (frontend/static/index.html): chat input plus the savings plan. Mode: Operate.
Audience today: hackathon judges watching a projected laptop demo; product users are new grads relocating.
Task: describe a move in plain English, answer a follow-up, read the plan, try what-ifs.
Constraints: data arrives through frontend/adapter.py's normalized plan; required fields only must still
render; the agent may fail or rate-limit; mock data must be labeled.

## Direction contract

THESIS: Your move is a trip, so the plan is a boarding pass: origin to destination, departs on your date, the fare is what you save. Refuses the category default of white KPI tiles plus a line chart.

OWN-WORLD: The brand logo's colours (binding, PRODUCT.md): a deep logo-blue shell (#0B3A8F) over a cool pale-blue ground, ticket-white cards, the logo's blue-to-violet gradient only on the pass's header band and the route arrow, teal (#00989F, light #7FD3C9) for money saved and progress, the wordmark orange (#FF924F) for the primary action, red only for warnings. Barlow Condensed for codes, labels and figures (tabular), Barlow for reading, Poppins Bold only in the wordmark. Perforated stub edges and tracked uppercase field labels, as on a real pass.

STORY: The visitor types their situation, sees a follow-up question when something is missing, then reads one number (the fare) and the monthly amount, the cost breakdown, and warnings. A what-if re-issues the pass and shows what changed.

FIRST VIEWPORT: Navy top bar (brand left; what-if chips and Start over right). Left column 440px white: "Your situation", the chat thread, input pinned at the bottom. Right: the pass, main panel with CHI → SEA city codes at 120px, departs/months/seat fields; stub with "Fare to save" at 96px and $/month. Below: five cost cards, then warnings. Primary action: the chat Send button.

FORM: Boarding pass, the IMPECCABLE’S PICK card (my rank 1 of 7), seed:efa70e1249530f2f. Signature move: the stub's barcode is the savings schedule, one bar per month whose height is the running total saved, rising to the dashed goal line (red when the plan falls short). A what-if re-issues the pass: the fare change is shown as old fare struck through beside the new one.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- No logo exists; the wordmark is set in type.
- The real agent (agent.py) does not exist yet; mock mode must stay labeled.
