# Coach Console — UX design

The athlete app is a phone-first "what do I do today?" tool. The console is a **desktop-first,
data-dense** tool answering **"across my clients, who needs me and what should I change?"** These
are different products, hence the separate app.

Design principles: **triage over dashboards** (surface who needs attention, don't make the coach
hunt); **keyboard-first** (coaches process many clients fast — j/k to move, Enter to open, review
shortcuts); **one screen per decision** (a check-in review shows everything needed to decide
*without* navigating away); **prescribe in context** (adjustments happen where the data is, not in a
separate module).

---

## 1. Roster — the command center (home)

A dense table/grid, one row per active client, **sorted "needs attention first."** Each row:

- name · current **phase + week** (e.g. "Prep · wk 6/16")
- **bodyweight trend** sparkline + rate %/wk (green on-plan, amber/red off-plan)
- **days since last check-in** (amber if due, red if overdue)
- **adherence** (nutrition / training / doses) as compact meters
- an **alert badge** — count of open flags (see §4)

Filters: needs-review, alerts, phase type, prep vs off-season. Bulk-nothing; this is a triage list.
A row expands to the composed **overview** (`clients/<id>/overview/`) for a quick peek; clicking the
name opens the full **client workspace**.

Top actions: **Invite client** (by email), pending invites, and a caseload summary (active clients,
check-ins due today, open alerts).

---

## 2. Check-in inbox + review (the weekly loop — the core)

Physique coaching *is* the weekly check-in: review data, course-correct before momentum dies, update
targets. The console makes that a first-class workflow, not a scavenger hunt.

**Inbox:** clients with a submitted or due check-in, ordered by due/overdue, with a one-line
delta (weight, adherence) so the coach can prioritize.

**Review — one screen, everything to decide:**
- **Bodyweight:** trend + EWMA + **rate %/wk** vs the phase's target rate.
- **Photos:** front/side/back **side-by-side vs the previous check-in** (the single most-used
  coaching artifact).
- **Measurements:** deltas since last (waist, arms, thighs, …).
- **Wellbeing:** energy/sleep/mood/motivation/soreness (small radar or bars) + BP / resting pulse.
- **Training:** output + adherence (sessions hit, volume, key-lift e1RM movement).
- **Nutrition:** adherence vs target; **adaptive-TDEE** readout with a suggested calorie move.
- **Doses:** adherence; any missed/rotated.
- **Bloodwork:** any new panel with flags inline.

**Respond in place:** a feedback box (stored comment → athlete sees it) **and** the adjustment
controls right there — bump calories/macros, add a phase adjustment, tweak a training day — then
**Mark reviewed**. The whole loop happens on one screen.

---

## 3. Client workspace (deep dive)

Opened from a name. Left nav = domains, coach-oriented (read unless noted):

- **Overview** — composition, adaptive TDEE, current prescriptions, recent activity, open alerts.
- **Nutrition** — target vs logged adherence over time; macro/micro/water; **edit target** (write).
- **Training** — current program; e1RM per lift, weekly volume per muscle, PRs, history; **build/edit
  program** (write, reuses `ProgramBuilder`).
- **Protocols** — active protocol; dose adherence; **concentration/release curves**; site rotation;
  **build/edit protocol** (write, reuses `ProtocolBuilder`).
- **Bloodwork** — results table (SI units/ranges), trends, derived (free-T, eGFR), out-of-range flags.
- **Progress** — photo timeline + compare; measurements; bodyweight EWMA.
- **Phases** — periodization timeline; **create/activate phase**; **add phase adjustment** that swaps
  program/target/protocol at a dated boundary (highest-leverage write).
- **Analysis** — body-analysis read; the parked deviation engine slots in here later.
- **History/Notes** — check-in history with the coach's feedback log.

The cross-domain framing is deliberate: bloodwork sits next to protocols and bodyweight, not siloed —
so an enhanced-athlete coach can reason about the whole picture at once.

---

## 4. Alerts & safety monitor (the differentiator)

A feed (per client) and a roster-wide panel of flags a busy coach would miss:

- **Bloodwork out of range** — hematocrit/HCT, lipids, ALT/AST, eGFR, estradiol, etc.
- **Blood pressure** trending up.
- **Rapid bodyweight change** (too fast a cut/gain vs the phase target).
- **Low adherence** (nutrition/training/doses below threshold).
- **Overdue check-in** / **overdue bloodwork**.

This is uniquely valuable for enhanced athletes and is precisely what generic coaching platforms
don't do. Thresholds live server-side (shared with the athlete app); the console badges and
explains them.

---

## 5. Prescription flows (write)

All reuse the athlete app's builders, coach-scoped via `X-Acting-Client`, and all authorized by the
existing `prescription_write` endpoints:

- **Nutrition target** — calories/macros/fiber/water + optional micro min–max → create + activate.
- **Program** — days/slots/exercises/planned sets → activate (single-active invariant server-side).
- **Protocol** — compounds/supplements, cadence, timing, route.
- **Phase + adjustment** — the periodization spine; swap program/target/protocol at a dated boundary.

Every write shows a clear "you are editing <client>'s plan" context and an undo/confirm, because the
coach is changing someone else's program.

---

## Brand & layout

Reuse the TML Signal tokens (orange→red gradient, per-domain accents, status green/amber/red) but a
**desktop, information-dense** treatment: tables, compact multi-series charts, split panes,
keyboard navigation. It should feel like a professional console, not a scaled-up phone screen.
