"""Relocation Savings Planner — Streamlit UI.  Run from repo root: streamlit run frontend/app.py"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Import frontend modules (mock_agent) and backend modules at the repo root (agent.py).
_HERE = Path(__file__).resolve().parent
for _p in (_HERE.parent, _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import altair as alt
import pandas as pd
import streamlit as st

from adapter import normalize

# Flip to False once the Gemini lane exposes agent.respond(messages) per contract.py.
USE_MOCK = True
if USE_MOCK:
    from mock_agent import respond
else:
    from agent import respond  # noqa: F401

EXAMPLES = [
    "I'm graduating in May, making 85k in Chicago, $20k in student loans, "
    "want to move to Seattle by September, open to a roommate.",
    "New job in NYC paying $70k, I live in Austin, no debt, $2k saved, moving by August.",
    "I want to move to Denver.",
]

st.set_page_config(page_title="Relo AI · Relocation Savings Planner", page_icon="🧳", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem;}
      .hero {border-radius: 14px; padding: 1.4rem 1.6rem; margin-bottom: 1rem;
             background: linear-gradient(135deg, #0f766e 0%, #155e75 100%); color: #fff;}
      .hero .label {font-size: .85rem; opacity: .85; text-transform: uppercase; letter-spacing: .06em;}
      .hero .big {font-size: 2.4rem; font-weight: 700; line-height: 1.15; margin: .25rem 0;}
      .hero .sub {font-size: 1.05rem; opacity: .95;}
      .pill {display:inline-block; font-size:.72rem; padding:1px 8px; border-radius:999px;
             background:#fef3c7; color:#92400e; margin-left:6px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- state ----------
if "messages" not in st.session_state:
    st.session_state.messages = []  # [{"role", "content"}]
if "plan" not in st.session_state:
    st.session_state.plan = None
if "prev_plan" not in st.session_state:
    st.session_state.prev_plan = None


def send(text: str) -> None:
    st.session_state.messages.append({"role": "user", "content": text})
    try:
        with st.spinner("Crunching real numbers…"):
            result = normalize(respond(st.session_state.messages))
    except Exception as e:  # keep the demo alive on rate limits etc.
        st.session_state.messages.append(
            {"role": "assistant", "content": f"⚠️ Something went wrong: {e}. Try again in a moment."}
        )
        return
    st.session_state.messages.append({"role": "assistant", "content": result["message"]})
    if result["type"] == "plan":
        st.session_state.prev_plan = st.session_state.plan
        st.session_state.plan = result["plan"]


def money(x: float) -> str:
    return f"${x:,.0f}"


# ---------- sidebar ----------
with st.sidebar:
    st.header("🧳 Relo AI")
    st.caption("Tell us your situation in plain English. We'll tell you how much to save, and by when.")
    st.subheader("Try an example")
    for i, ex in enumerate(EXAMPLES):
        if st.button(ex, key=f"ex{i}", width="stretch"):
            st.session_state.messages, st.session_state.plan, st.session_state.prev_plan = [], None, None
            send(ex)
    st.divider()
    if st.session_state.plan:
        st.subheader("What if…")
        for q in ["What if I skip the roommate?", "What if I get a roommate?", "What if I move in December?"]:
            if st.button(q, key=q, width="stretch"):
                send(q)
        st.divider()
    if st.button("📦 Load sample backend data", width="stretch"):
        from sample_data import SAMPLE_RESPONSE

        result = normalize(SAMPLE_RESPONSE)
        st.session_state.messages = [
            {"role": "user", "content": "*(Loaded sample backend response)*"},
            {"role": "assistant", "content": result["message"]},
        ]
        st.session_state.plan, st.session_state.prev_plan = result["plan"], None
    if st.button("Start over", type="secondary", width="stretch"):
        st.session_state.messages, st.session_state.plan, st.session_state.prev_plan = [], None, None
        st.rerun()
    if USE_MOCK:
        st.caption("🧪 Running on **mock data**. Numbers are placeholders.")


# ---------- layout ----------
chat_col, plan_col = st.columns([2, 3], gap="large")

with chat_col:
    st.subheader("Your situation")
    if not st.session_state.messages:
        st.info(
            "Describe your move in one paragraph: your **job & salary**, **where you live now**, "
            "**debt**, **bills**, **where you're going**, and **when**."
        )
    for m in st.session_state.messages:
        with st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else "🧳"):
            st.markdown(m["content"])

prompt = st.chat_input("e.g. Making 85k, moving from Chicago to Seattle by September with a roommate…")
if prompt:
    send(prompt)
    st.rerun()


def render_plan(plan: dict, prev: dict | None) -> None:
    deadline = date.fromisoformat(plan["deadline"])
    prof = plan["profile"]
    route = (f" · {prof.get('current_city', '?')} → {prof['target_city']}"
             if prof.get("target_city") else "")

    st.markdown(
        f"""
        <div class="hero">
          <div class="label">Your savings target</div>
          <div class="big">{money(plan['target_total'])} by {deadline:%B %-d, %Y}</div>
          <div class="sub">Save <b>{money(plan['monthly_savings'])}/month</b> starting now
          · {plan['months_to_save']} months{route}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    b = plan["monthly_budget"]
    leftover = b["take_home"] - b["rent"] - b["bills"] - b["debt_payment"]

    def delta(key: str, getter=lambda p, k: p[k]):
        if not prev:
            return None
        d = getter(plan, key) - getter(prev, key)
        return None if d == 0 else f"{'+' if d > 0 else '−'}{money(abs(d))}"

    rent_get = lambda p, k: p["monthly_budget"][k]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total needed", money(plan["target_total"]), delta("target_total"), delta_color="inverse")
    c2.metric("Save / month", money(plan["monthly_savings"]), delta("monthly_savings"), delta_color="inverse")
    c3.metric("New rent / month", money(b["rent"]), delta("rent", rent_get), delta_color="inverse")
    c4.metric("Rent share of pay", f"{b['rent'] / b['take_home']:.0%}")

    for w in plan["warnings"]:
        {"error": st.error, "warning": st.warning}.get(w["level"], st.info)(w["text"])

    tab_names = ["💸 Move-in costs", "📈 Savings plan", "🏠 Monthly budget"]
    if prof:
        tab_names.append("🔍 What we understood")
    tabs = st.tabs(tab_names)
    tab_costs, tab_chart, tab_budget = tabs[:3]

    with tab_costs:
        df = pd.DataFrame(plan["move_in_costs"])
        if df.empty:
            st.caption("No itemized costs came back.")
        else:
            df["Item"] = df["label"]
            if "estimate" in df:
                df["Item"] += df["estimate"].map(lambda e: " (estimate)" if e else "")
            cols = ["Item", "amount"] + (["source"] if "source" in df else [])
            st.dataframe(
                df[cols],
                hide_index=True,
                width="stretch",
                column_config={
                    "amount": st.column_config.ProgressColumn(
                        "Amount", format="$%d", min_value=0, max_value=int(df["amount"].max())
                    ),
                    "source": st.column_config.TextColumn("Source"),
                },
            )
            itemized = df["amount"].sum()
            st.markdown(f"**Total one-time cost: {money(itemized)}**")
            if abs(plan["target_total"] - itemized) >= 1:
                diff = plan["target_total"] - itemized
                st.caption(
                    f"Your total needed ({money(plan['target_total'])}) is "
                    f"{money(abs(diff))} {'more' if diff > 0 else 'less'} than these itemized costs."
                )
        if prof.get("current_savings"):
            st.caption(f"You already have {money(prof['current_savings'])} saved, which counts toward this.")

    with tab_chart:
        start = date.today().replace(day=1)
        months = plan["months_to_save"]
        rows = []
        for i in range(months + 1):
            y, m = divmod(start.month - 1 + i, 12)
            rows.append({
                "Month": date(start.year + y, m + 1, 1),
                "Saved": min(plan["target_total"],
                             prof.get("current_savings", 0) + plan["monthly_savings"] * i),
            })
        sdf = pd.DataFrame(rows)
        area = alt.Chart(sdf).mark_area(
            line={"color": "#0f766e"}, color="#0f766e", opacity=0.25, point=True
        ).encode(
            x=alt.X("Month:T", title=None, axis=alt.Axis(format="%b %Y")),
            y=alt.Y("Saved:Q", title="Saved ($)", axis=alt.Axis(format="$,.0f")),
            tooltip=[alt.Tooltip("Month:T", format="%B %Y"), alt.Tooltip("Saved:Q", format="$,.0f")],
        )
        goal = alt.Chart(pd.DataFrame({"y": [plan["target_total"]]})).mark_rule(
            color="#dc2626", strokeDash=[6, 4]
        ).encode(y="y:Q")
        label = alt.Chart(pd.DataFrame({"y": [plan["target_total"]], "x": [sdf["Month"].iloc[0]]})).mark_text(
            text=f"Goal {money(plan['target_total'])}", align="left", dy=-8, color="#dc2626"
        ).encode(x="x:T", y="y:Q")
        st.altair_chart((area + goal + label).properties(height=320), use_container_width=True)

    with tab_budget:
        colors = {"Rent": "#155e75", "Bills": "#0891b2", "Debt payments": "#f59e0b", "Left over": "#10b981"}
        bdf = pd.DataFrame([
            {"Category": "Rent", "Amount": b["rent"]},
            {"Category": "Bills", "Amount": b["bills"]},
            {"Category": "Debt payments", "Amount": b["debt_payment"]},
            {"Category": "Left over", "Amount": max(0, leftover)},
        ])
        bdf = bdf[(bdf["Amount"] > 0) | (bdf["Category"].isin(["Rent", "Left over"]))]
        bar = alt.Chart(bdf).mark_bar(cornerRadius=4).encode(
            x=alt.X("Amount:Q", title=None, axis=alt.Axis(format="$,.0f")),
            y=alt.Y("Category:N", sort=None, title=None),
            color=alt.Color("Category:N", legend=None,
                            scale=alt.Scale(domain=list(colors), range=list(colors.values()))),
            tooltip=["Category", alt.Tooltip("Amount:Q", format="$,.0f")],
        ).properties(height=50 * len(bdf) + 20)
        st.altair_chart(bar, use_container_width=True)
        where = f" in {prof['target_city']}" if prof.get("target_city") else ""
        st.caption(f"Based on estimated take-home pay of **{money(b['take_home'])}/month**{where}.")
        if leftover < 0:
            st.error(f"You'd be {money(-leftover)}/month short after the move.")

    if prof:
        with tabs[3]:
            st.caption("Check that we read your situation right. Fix anything in the chat.")
            fields = [
                ("Salary", "salary", money), ("Moving from", "current_city", str),
                ("Moving to", "target_city", str), ("Debt", "debt", money),
                ("Monthly bills", "monthly_bills", money), ("Already saved", "current_savings", money),
                ("Roommate", "roommate", lambda v: "Yes" if v else "No"),
            ]
            rows = [(label, fmt(prof[k])) for label, k, fmt in fields if k in prof]
            rows.append(("Move by", f"{deadline:%B %Y}"))
            st.table(pd.DataFrame(rows, columns=["", "Value"]).set_index(""))


with plan_col:
    if st.session_state.plan:
        render_plan(st.session_state.plan, st.session_state.prev_plan)
    else:
        st.subheader("Your plan")
        st.markdown(
            """
            Your plan will appear here:

            - **One number:** how much to save, and by when
            - **Move-in costs:** rent, deposit, movers, furniture, the gap before your first paycheck
            - **Warnings:** rent over 30% of pay, NYC's 40x-rent rule, and more

            Every dollar figure comes from a data source, not a guess.
            """
        )
