---
name: reloai boarding pass
surface: frontend/static (index.html, styles.css, app.js)
---

# reloai design system

The plan is a **boarding pass**: origin to destination, departs on the move date, the fare is the amount to
save. The colours come from the reloai logo (PRODUCT.md, Brand Commitments). Tokens live at the top of
`frontend/static/styles.css`; change them there, never inline.

## Colors

| Token | Value | Job |
|---|---|---|
| `--shell` | `#0B3A8F` | Top bar, user chat bubbles. The logo's deep blue. |
| `--ground` | `#EDF1F9` | Page ground behind the pass and cards. |
| `--paper` / `--paper-2` | `#FFFFFF` / `#F6F8FC` | Pass main panel, cards / pass stub, bot bubbles. |
| `--ink` / `--ink-2` / `--ink-3` | `#0E1B3D` / `#3E4A66` / `#5F6A85` | Text, secondary text, labels (all ≥4.5:1 on white). |
| `--grad` | `#0A4BAA → #6E5BC9 → #C66BE2` | The logo gradient. Only on the pass header band, the route line, the selected rank badge. |
| `--teal` / `--teal-ink` / `--teal-light` | `#00989F` / `#006E73` / `#7FD3C9` | Money saved: barcode bars, monthly amount, "left over". |
| `--orange` | `#FF924F` | The wordmark and the one primary action (Send), dark ink on top. Focus ring. Goal line. |
| `--red` + `--red-wash` | `#C42F28` / `#FCECEA` | Errors and blocking warnings only; rent share over 30%. |
| amber / violet washes | `#FFF2DE` / `#EFECFA` | Warning and info alerts; follow-up questions. |

Cost and budget series use the logo ramp in order: `#0A4BAA, #3F55BE, #6E5BC9, #9A63D6, #C66BE2, #00989F`.

## Typography

Self-hosted in `frontend/static/fonts/` (fonts.css).

- **Barlow Condensed** 500–800: city codes (120px), the fare (96px, 72px for 7+ characters), section
  headings (36px), field values, uppercase tracked field labels (16px, .12em). All figures tabular.
- **Barlow** 400–700: reading text, chat, list rows. Base 18px for projector legibility.
- **Poppins** 700: the wordmark only.

One ramp, fixed steps: 12, 14, 16, 18, 22, 28, 36, 48, 72, 96px (`--t-*`). No kicker/eyebrow above headings.

## Components

- **Pass**: main panel (gradient band, route, fields row) + stub (fare, monthly, barcode) split by a dashed
  perforation with round notches cut in the ground colour. Stub width `--stub-w` 340px; stacks under 680px.
- **Barcode (signature)**: one bar per month, height = running total saved; dashed goal line, red when short.
- **Re-issue**: a new plan after a what-if or a city switch prints the pass in (clip-path, 750ms ease-out),
  marks the band "Re-issued", strikes the old fare and shows the delta (teal down, red up).
- **City chooser**: ranked rows (rank badge, city + reasons, score, fare, per month); the selected row has a
  blue border and "On your pass".
- **Alerts**: full-border tinted boxes with a drawn icon; never a one-sided bar.
- **Chips / buttons**: 44px min height; hover lightens, press moves 1px.

## Motion and states

One authored moment (the pass printing in) plus message entrance and the typing dots. Everything stops under
`prefers-reduced-motion`. States covered: empty (blank pass), loading (typing), follow-up question, error
with retry, plan, re-issued plan, shortfall, mock-data badge.
