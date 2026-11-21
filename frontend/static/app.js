/* reloai front end. Talks to frontend/server.py:
 *   POST /api/respond {messages} -> {type:"question", message} | {type:"plan", message, plan}
 *   GET  /api/sample             -> the sample backend response, normalized
 *   GET  /api/config             -> {mock: bool}
 */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const els = {
    thread: $("#thread"), intro: $("#intro"), form: $("#composer"), input: $("#composer-input"),
    send: $("#send"), whatifs: $("#whatifs"), reset: $("#reset"), mockBadge: $("#mock-badge"),
    addRoommate: $("#add-roommate"),
    blank: $("#blank"), plan: $("#plan"), board: $("#board"), loadSample: $("#load-sample"),
  };

  const state = { messages: [], plan: null, prev: null, options: [], optIndex: 0, busy: false, mock: false };

  const CITY_CODES = {
    "new york": "NYC", "san francisco": "SFO", "seattle": "SEA", "austin": "AUS", "chicago": "CHI",
    "boston": "BOS", "denver": "DEN", "los angeles": "LAX", "atlanta": "ATL", "miami": "MIA",
    "washington": "WAS", "philadelphia": "PHL", "dallas": "DFW", "houston": "HOU", "portland": "PDX",
    "san diego": "SAN", "phoenix": "PHX", "minneapolis": "MSP", "detroit": "DTW", "nashville": "BNA",
    "boise": "BOI", "salt lake city": "SLC", "raleigh": "RDU", "pittsburgh": "PIT", "columbus": "CMH",
  };
  const COST_COLORS = ["#0A4BAA", "#3F55BE", "#6E5BC9", "#9A63D6", "#C66BE2", "#00989F", "#7FD3C9"];
  const BUDGET = [
    ["rent", "Rent", "#0A4BAA"], ["bills", "Bills", "#6E5BC9"],
    ["debt_payment", "Debt payments", "#C66BE2"], ["spending", "Spending", "#9A63D6"], ["left", "Left over", "#00989F"],
  ];
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- formatting ----------
  const money = (n) => "$" + Math.round(Math.abs(n)).toLocaleString("en-US");
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  const parseDate = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };
  const fmtDate = (d, opts) => d.toLocaleDateString("en-US", opts);
  const cityName = (c) => (c || "").split(",")[0].trim();
  const cityCode = (c) => {
    const n = cityName(c).toLowerCase();
    if (!n || n === "unknown" || n === "?") return null;
    if (CITY_CODES[n]) return CITY_CODES[n];
    const words = n.replace(/[^a-z ]/g, "").split(/\s+/).filter(Boolean);
    if (words.length > 1) return (words.map((w) => w[0]).join("") + words[words.length - 1].slice(-1)).slice(0, 3).toUpperCase();
    return n.replace(/[^a-z]/g, "").slice(0, 3).toUpperCase();
  };

  // ---------- chat ----------
  function addMessage(role, html, cls = "") {
    els.intro.hidden = true;
    const div = document.createElement("div");
    div.className = `msg ${role} ${cls}`.trim();
    div.innerHTML = html;
    els.thread.appendChild(div);
    els.thread.scrollTop = els.thread.scrollHeight;
    return div;
  }

  function setBusy(b) {
    state.busy = b;
    els.send.disabled = b;
    els.whatifs.querySelectorAll("button").forEach((x) => (x.disabled = b));
    els.thread.querySelectorAll(".example").forEach((x) => (x.disabled = b));
    updateRoommateButton(); // keeps it disabled at the max even when the rest re-enable
  }

  async function ask(text) {
    text = text.trim();
    if (!text || state.busy) return;
    state.messages.push({ role: "user", content: text });
    addMessage("user", esc(text));
    await run();
  }

  async function run() {
    setBusy(true);
    const typing = addMessage("bot", '<span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>Pricing your move…', "typing");
    try {
      const res = await fetch("/api/respond", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: state.messages }),
      });
      const data = await res.json().catch(() => ({}));
      typing.remove();
      if (!res.ok || data.error) throw new Error(data.error || `The server answered ${res.status}.`);
      state.messages.push({ role: "assistant", content: data.message });
      setSource(data.source);
      if (data.type === "question") {
        addMessage("bot", `<span class="q-label">Quick question</span>${md(data.message)}`, "question");
        els.input.focus();
      } else {
        addMessage("bot", md(data.message));
        showPlan(data.plan, data.options);
      }
    } catch (err) {
      typing.remove();
      const box = addMessage("bot", `${esc(err.message || "Something went wrong.")} Your message is saved.<br><button type="button">Try again</button>`, "error");
      box.querySelector("button").addEventListener("click", () => { box.remove(); run(); });
    } finally {
      setBusy(false);
    }
  }

  // ---------- plan ----------
  // ---------- roommates ----------
  const MAX_ROOMMATES = 3; // rent data goes up to 4 bedrooms, one per person
  const ORDINAL = ["", "", "2nd", "3rd"];
  function roommateCount() {
    const prof = (state.plan && state.plan.profile) || {};
    return Number.isFinite(prof.roommates) ? prof.roommates : (prof.roommate ? 1 : 0);
  }
  // Label the button for the next press: "Add a roommate", "Add a 2nd roommate", ... "3 roommates max".
  function updateRoommateButton() {
    const next = roommateCount() + 1;
    const atMax = next > MAX_ROOMMATES;
    els.addRoommate.disabled = atMax || state.busy;
    els.addRoommate.textContent = atMax ? `${MAX_ROOMMATES} roommates max`
      : next === 1 ? "Add a roommate" : `Add a ${ORDINAL[next]} roommate`;
  }
  function addRoommate() {
    const next = roommateCount() + 1;
    if (next > MAX_ROOMMATES) return;
    // Say the exact number, so each press adds one more instead of re-asking for "a roommate".
    ask(`What if I had ${next} roommate${next === 1 ? "" : "s"}? Keep everything else the same.`);
  }

  function showPlan(plan, options, index = 0) {
    state.prev = state.plan;
    state.plan = plan;
    if (options) { state.options = options; state.optIndex = index; }
    els.blank.hidden = true;
    els.plan.hidden = false;
    els.whatifs.hidden = false;
    els.reset.hidden = false;
    els.plan.innerHTML = renderPlan(plan, state.prev);
    updateRoommateButton();
    const pass = els.plan.querySelector(".pass");
    if (!reduceMotion) {
      pass.classList.remove("printing"); void pass.offsetWidth; pass.classList.add("printing");
      if (state.prev && state.prev.target_total !== plan.target_total) tween(els.plan.querySelector(".fare"), state.prev.target_total, plan.target_total);
    }
    if (window.innerWidth <= 1000) els.board.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  }

  function tween(el, from, to) {
    const t0 = performance.now(), dur = 700;
    const step = (t) => {
      const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 4);
      el.textContent = money(from + (to - from) * e);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function schedule(plan) {
    const start = new Date(); start.setDate(1);
    const saved0 = (plan.profile && plan.profile.current_savings) || 0;
    const rows = [];
    for (let i = 1; i <= plan.months_to_save; i++) {
      const d = new Date(start.getFullYear(), start.getMonth() + i - 1, 1);
      const saved = Math.min(plan.target_total, saved0 + plan.monthly_savings * i);
      rows.push({ d, saved });
    }
    return rows;
  }

  function fitsNote(p) {
    const c = p.current_budget;
    if (!c) return "";
    const fits = c.surplus >= p.monthly_savings;
    return `<p class="fits ${fits ? "ok" : "bad"}">Right now you have <b>${money(c.surplus)}</b> a month left after costs. ${
      fits ? `Saving ${money(p.monthly_savings)} a month fits.` : `Saving ${money(p.monthly_savings)} a month doesn't fit yet.`}</p>`;
  }

  // Why the selected town got its score: each factor's points, its share of the score, and the reason.
  function renderBreakdown(o) {
    const parts = o.score_breakdown || [];
    if (!parts.length) return "";
    const sum = parts.map((b) => `${b.points} × ${b.weight}%`).join(" + ");
    const rows = parts.map((b) => `<span class="bd-row">
        <span class="bd-factor">${esc(b.factor)}</span>
        <span class="bd-pts"><b>${b.points}</b>/100 · ${b.weight}% of score</span>
        <span class="bd-detail">${esc(b.detail)}</span>
      </span>`).join("");
    return `<span class="opt-breakdown">
      <span class="bd-head">Why ${o.score ?? "–"}: ${esc(sum)}</span>${rows}</span>`;
  }

  function renderOptions() {
    const opts = state.options;
    if (!opts || opts.length < 2) return "";
    const rows = opts.map((o, i) => {
      const on = i === state.optIndex;
      const job = o.salary ? `Job${o.work_city ? ` in ${esc(o.work_city)}` : ""} at ${money(o.salary)}` : "";
      const reasons = o.reasons.filter((r) => !/^Job in /.test(r));
      return `<li><button type="button" class="opt${on ? " on" : ""}" data-opt="${i}" aria-pressed="${on}">
        <span class="opt-rank">${o.rank ?? i + 1}</span>
        <span class="opt-city"><span class="opt-name">${esc(o.city)}</span><span class="opt-why">${[job, ...reasons].filter(Boolean).map(esc).join(" · ")}</span></span>
        <span class="opt-num opt-score"><span class="label">Score</span><b>${o.score ?? "–"}</b></span>
        <span class="opt-num opt-fare"><span class="label">Fare</span><b>${money(o.plan.target_total)}</b></span>
        <span class="opt-num opt-month"><span class="label">Per month</span><b>${money(o.plan.monthly_savings)}</b></span>
        <span class="opt-tag">${on ? "On your pass" : "Show this"}</span>
        ${on ? renderBreakdown(o) : ""}
      </button></li>`;
    }).join("");
    return `<section class="sec options" aria-labelledby="h-options">
      <div class="sec-head"><h2 id="h-options">Where you could live</h2><span class="sec-aside">Ranked for you · pick one to see its pass</span></div>
      <ol class="opts">${rows}</ol></section>`;
  }

  function renderPlan(p, prev) {
    const prof = p.profile || {};
    const deadline = parseDate(p.deadline);
    const b = p.monthly_budget;
    const left = "leftover" in b ? b.leftover : b.take_home - b.rent - (b.bills || 0) - (b.debt_payment || 0) - (b.spending || 0);
    const opt = state.options[state.optIndex];
    const rentShare = b.take_home ? b.rent / b.take_home : 0;
    const from = cityCode(prof.current_city), to = cityCode(prof.target_city);
    const issued = fmtDate(new Date(), { month: "short", day: "numeric", year: "numeric" });

    // route
    let route;
    if (to && !from) {
      route = `<div class="route one-way"><div class="city">
        <span class="label">Destination</span><div class="code">${esc(to)}</div><div class="name">${esc(prof.target_city)}</div></div></div>`;
    } else if (to) {
      route = `<div class="route">
        <div class="city from"><div class="code">${esc(from || "···")}</div><div class="name">${esc(cityName(prof.current_city) || "Where you are now")}</div></div>
        <div class="flight" aria-hidden="true"><span class="track"></span><svg><use href="#i-plane"/></svg><span class="track"></span></div>
        <div class="city to"><div class="code">${esc(to)}</div><div class="name">${esc(cityName(prof.target_city))}</div></div>
      </div>`;
    } else {
      route = `<div class="route no-cities"><div class="solo-title">Your move</div></div>`;
    }

    // fields
    const fields = [["Departs", fmtDate(deadline, { month: "short", day: "numeric", year: "numeric" })], ["Months", String(p.months_to_save)]];
    if ("roommate" in prof) fields.push(["Seat", prof.roommate ? "Roommate" : "Solo"]);
    if (opt && opt.work_city && opt.miles_from_work) fields.push(["Commute", `${Math.round(opt.miles_from_work)} mi`]);
    fields.push(["Rent share", `${Math.round(rentShare * 100)}%`, rentShare > 0.3]);

    // fare change
    let was = "";
    if (prev && prev.target_total !== p.target_total) {
      const diff = p.target_total - prev.target_total;
      was = `<div class="fare-was"><s>${money(prev.target_total)}</s><span class="delta ${diff < 0 ? "down" : "up"}">${diff < 0 ? "−" : "+"}${money(diff)}</span></div>`;
    }

    // barcode
    const rows = schedule(p);
    const reached = rows.length ? rows[rows.length - 1].saved : 0;
    const short = (p.shortfall || 0) > 0;
    const top = short ? p.target_total : Math.max(reached, 1);
    const bars = rows.map((r, i) => {
      const label = `${fmtDate(r.d, { month: "short", year: "numeric" })}: ${money(r.saved)} saved`;
      return `<span class="bar${i === rows.length - 1 ? " last" : ""}" style="height:${(r.saved / top) * 100}%" title="${esc(label)}"></span>`;
    }).join("");
    const axisStart = rows.length ? fmtDate(rows[0].d, { month: "short", year: "2-digit" }) : "";
    const axisEnd = fmtDate(deadline, { month: "short", year: "2-digit" });
    const codeLabel = short
      ? `Savings schedule: ${money(reached)} by ${fmtDate(deadline, { month: "long", year: "numeric" })}, ${money(p.target_total - reached)} short of the goal.`
      : `Savings schedule: ${p.months_to_save} monthly deposits reaching ${money(p.target_total)}.`;

    // costs
    const costs = p.move_in_costs || [];
    const itemized = costs.reduce((s, c) => s + c.amount, 0);
    const maxCost = Math.max(1, ...costs.map((c) => c.amount));
    const strip = costs.map((c, i) => `<span style="flex:${c.amount};background:${COST_COLORS[i % COST_COLORS.length]}" title="${esc(c.label)}: ${money(c.amount)}"></span>`).join("");
    const costRows = costs.map((c, i) => {
      const size = 1.375 + (c.amount / maxCost) * 0.875; // magnitude ramp: 22px → 36px
      return `<li class="cost"><span class="sw" style="background:${COST_COLORS[i % COST_COLORS.length]}"></span>
        <span class="what">${esc(c.label)}${c.estimate ? '<span class="tag">Estimate</span>' : ""}${c.source ? `<span class="src">${esc(c.source)}</span>` : ""}</span>
        <span class="amt" style="font-size:${size.toFixed(3)}rem">${money(c.amount)}</span></li>`;
    }).join("");
    let costNote = "";
    if (costs.length && Math.abs(p.target_total - itemized) >= 1) {
      const d = p.target_total - itemized;
      costNote = `<p class="sec-note">Your total needed (${money(p.target_total)}) is ${money(d)} ${d > 0 ? "more" : "less"} than these itemized costs.</p>`;
    } else if (prof.current_savings) {
      costNote = `<p class="sec-note">You already have ${money(prof.current_savings)} saved, which counts toward this.</p>`;
    }

    // warnings
    const icon = { error: "i-stop", warning: "i-alert", info: "i-info" };
    const alerts = (p.warnings || []).map((w) =>
      `<li class="alert ${esc(w.level)}"><svg aria-hidden="true"><use href="#${icon[w.level] || "i-info"}"/></svg><span>${md(w.text)}</span></li>`).join("");

    // budget
    const parts = { rent: b.rent, bills: b.bills || 0, debt_payment: b.debt_payment || 0, spending: b.spending || 0, left: Math.max(0, left) };
    const budgetBar = BUDGET.filter(([k]) => parts[k] > 0).map(([k, l, c]) => `<span style="flex:${parts[k]};background:${c}" title="${l}: ${money(parts[k])}"></span>`).join("");
    const legend = BUDGET.filter(([k]) => parts[k] > 0 || k === "rent" || k === "left")
      .map(([k, l, c]) => `<li><span class="sw" style="background:${c}"></span><span>${l}</span><span class="v">${money(parts[k])}</span></li>`).join("");
    const where = prof.target_city ? ` in ${esc(cityName(prof.target_city))}` : "";

    // details
    const det = [
      ["Salary", "salary", money], ["From", "current_city", String], ["To", "target_city", String],
      ["Debt", "debt", money], ["Bills", "monthly_bills", (v) => `${money(v)} / month`],
      ["Already saved", "current_savings", money], ["Roommate", "roommate", (v) => (v ? "Yes" : "No")],
    ].filter(([, k]) => k in prof).map(([l, k, f]) => `<dt>${l}</dt><dd>${esc(f(prof[k]))}</dd>`).join("");

    const fieldsHtml = fields.map(([k, v, bad]) => `<div class="field"><dt>${k}</dt><dd${bad ? ' class="bad"' : ""}>${esc(v)}</dd></div>`).join("");

    return `<div class="plan-wrap">${renderOptions()}
      <article class="pass" aria-label="Your relocation plan">
        <div class="pass-main">
          <div class="pass-band"><span>Relocation pass</span>${prev ? '<span class="reissued">Re-issued</span>' : `<span>Issued ${esc(issued)}</span>`}</div>
          ${route}
          <dl class="fields">${fieldsHtml}</dl>
        </div>
        <div class="stub">
          <span class="label">Fare to save</span>
          <div class="fare${money(p.target_total).length > 6 ? " long" : ""}">${money(p.target_total)}</div>
          ${was}
          <p class="monthly"><b>${money(p.monthly_savings)}</b> / month<span>for ${p.months_to_save} month${p.months_to_save === 1 ? "" : "s"}, starting now</span></p>
          <div class="barcode">
            <div class="bars" role="img" aria-label="${esc(codeLabel)}"><span class="goal${short ? " short" : ""}"></span>${bars}</div>
            <div class="bar-axis"><span>${esc(axisStart)}</span><span>${esc(axisEnd)}</span></div>
          </div>
        </div>
      </article>

      ${alerts ? `<section class="sec" aria-labelledby="h-alerts"><div class="sec-head"><h2 id="h-alerts">Heads up</h2></div><ul class="alerts">${alerts}</ul></section>` : ""}

      <section class="sec" aria-labelledby="h-costs">
        <div class="sec-head"><h2 id="h-costs">Move-in costs</h2><span class="total">${money(itemized)}</span></div>
        ${costs.length ? `<div class="strip" aria-hidden="true">${strip}</div><ul class="costs">${costRows}</ul>` : '<p class="sec-note">No itemized costs came back.</p>'}
        ${costNote}
      </section>

      <div class="split">
        <section class="sec card" aria-labelledby="h-budget">
          <div class="sec-head"><h2 id="h-budget">Each month after the move</h2></div>
          <div class="budget-bar" aria-hidden="true">${budgetBar}</div>
          <ul class="legend">${legend}<li class="take"><span></span><span>Take-home pay${where}</span><span class="v">${money(b.take_home)}</span></li></ul>
          ${left < 0 ? `<p class="short-note">You'd be ${money(-left)} short every month after the move.</p>` : ""}
          ${fitsNote(p)}
        </section>
        ${det ? `<section class="sec card" aria-labelledby="h-details"><div class="sec-head"><h2 id="h-details">What I understood</h2></div><dl class="details">${det}</dl><p class="sec-note">Something off? Correct it in the chat.</p></section>` : ""}
      </div>

      <p class="footnote">${state.mock ? "Mock data: these numbers are placeholders, not your plan." : "Every dollar figure comes from a data tool, not the AI. Estimates are marked."}</p>
    </div>`;
  }

  function setSource(source) {
    if (!source) return;
    state.mock = source === "mock";
    els.mockBadge.hidden = !state.mock;
  }

  // ---------- reset / sample ----------
  function reset() {
    state.messages = []; state.plan = null; state.prev = null; state.options = []; state.optIndex = 0;
    els.thread.querySelectorAll(".msg").forEach((m) => m.remove());
    els.intro.hidden = false;
    els.plan.hidden = true; els.plan.innerHTML = "";
    els.blank.hidden = false;
    els.whatifs.hidden = true; els.reset.hidden = true;
    updateRoommateButton();
    els.input.value = ""; els.input.focus();
  }

  async function loadSample(name = "options") {
    reset();
    try {
      const data = await (await fetch(`/api/sample?name=${encodeURIComponent(name)}`)).json();
      state.messages.push({ role: "user", content: "(Loaded the sample backend response)" }, { role: "assistant", content: data.message });
      addMessage("user", "<em>Loaded the sample backend response</em>");
      addMessage("bot", md(data.message));
      setSource("sample");
      showPlan(data.plan, data.options);
    } catch {
      addMessage("bot", "Couldn't load the sample. Is the server running?", "error");
    }
  }

  // ---------- wiring ----------
  els.form.addEventListener("submit", (e) => { e.preventDefault(); const t = els.input.value; els.input.value = ""; autosize(); ask(t); });
  els.input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); els.form.requestSubmit(); } });
  const autosize = () => { els.input.style.height = "auto"; els.input.style.height = Math.min(200, els.input.scrollHeight + 2) + "px"; };
  els.input.addEventListener("input", autosize);
  document.querySelectorAll(".example").forEach((b) => b.addEventListener("click", () => ask(b.dataset.text)));
  els.whatifs.addEventListener("click", (e) => {
    if (e.target.closest("#add-roommate")) return addRoommate();
    const b = e.target.closest("[data-ask]"); if (b) ask(b.dataset.ask);
  });
  els.reset.addEventListener("click", reset);
  els.loadSample.addEventListener("click", () => loadSample());
  els.plan.addEventListener("click", (e) => {
    const b = e.target.closest("[data-opt]");
    if (!b || state.busy) return;
    const i = Number(b.dataset.opt);
    if (i === state.optIndex) return;
    showPlan(state.options[i].plan, state.options, i);
    const name = state.options[i].city;
    addMessage("bot", md(`Showing **${name}**: ${money(state.plan.target_total)} by your move date, ${money(state.plan.monthly_savings)}/month.`));
  });

  fetch("/api/config").then((r) => r.json()).then((c) => { state.mock = !!c.mock; els.mockBadge.hidden = !state.mock; }).catch(() => {});
  // A sample response is the teammate's real backend output: label it as such, not as mock.

  // Demo shortcuts: /#sample loads the sample response; /#ask=<text>||<text> sends messages in order on load.
  const hash = decodeURIComponent(location.hash.slice(1));
  if (hash === "sample" || hash.startsWith("sample=")) loadSample(hash.split("=")[1] || "options");
  else if (hash.startsWith("ask=")) (async () => { for (const t of hash.slice(4).split("||")) await ask(t); })();
})();
