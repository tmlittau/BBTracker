# TML Signal — Coach Console — Implementation Plan

A phased plan for a **standalone, coach-first web app** over the existing Django/DRF backend.
Read alongside [`BACKEND_CAPABILITIES.md`](BACKEND_CAPABILITIES.md) (what the API already provides
+ the small additions needed) and [`COACH_UX.md`](COACH_UX.md) (screen-by-screen design).

---

## Guiding principles

1. **Coach-first, not athlete-app-reused.** The information architecture is a **roster → triage →
   review → prescribe** loop over many clients, not the single-user tabs of the athlete app.
2. **One backend, thin client.** Business logic (adherence, TDEE, concentration curves, bloodwork
   flags, composition) stays server-side. This app reads the API and renders; it never re-derives.
3. **Reuse the backend's access model verbatim.** Every per-client call carries
   `X-Acting-Client: <id>`; the server authorizes it (reads for any active link, writes only for
   prescription endpoints with `can_edit_prescriptions`). The client can never see another client.
   See [`BACKEND_CAPABILITIES.md`](BACKEND_CAPABILITIES.md).
4. **Exploit the cross-domain data.** The reason to build this instead of buying TrueCoach: show
   training + nutrition + PED/bloodwork + periodization **together**, and prescribe against it.
5. **Prescribe on the server; the athlete's device pulls it.** The write direction of coaching is
   server-authoritative (phases/targets/programs/protocols). This must reconcile with the athlete
   app's local-first model — the single most important architectural item, in
   [`BACKEND_CAPABILITIES.md` §Sync & authority](BACKEND_CAPABILITIES.md).

---

## Prerequisites (before Phase 0)

| Item | Why it blocks |
|------|---------------|
| **Merge + deploy `coaching-stack`** | The entire coaching API (CoachClientLink, `resolve_effective_owner`, `/api/v1/coaching/*`, prescription-write scope) is parked, unmerged, and **not on the deployed backend**. Nothing here works until it ships. It is a large but complete, tested branch. |
| **Confirm the sync/authority model** | With the athlete app now local-first, verify the server's relational tables are populated from device backups (so coach reads see real data) **and** decide how coach prescriptions reach the device. See [`BACKEND_CAPABILITIES.md`](BACKEND_CAPABILITIES.md). This is a design decision, not code, but it gates a working loop. |
| **Auth + hosting decision** | App-token (`X-Session-Token`) vs same-origin session cookie; static SPA behind Caddy vs subdomain. Recommended defaults below. |
| **Tooling** | Node 20+, the SvelteKit toolchain (mirrors the athlete web app). |

---

## Tech + delivery decisions (recommended)

- **SvelteKit + Svelte 5 (runes) + Tailwind v4**, `adapter-static` → a **static SPA**. Maximizes
  reuse of the athlete web app's design system, API clients, `acting.ts`, and the extracted
  `ProgramBuilder` / `ProtocolBuilder`. No SSR node service to run (keeps the "backend-only" prod
  lean — Caddy serves the built files).
- **Auth: allauth headless *app* token** (`POST /_allauth/app/v1/auth/login` → `X-Session-Token`),
  same mechanism the iOS app uses and already live on `main` (`XSessionTokenAuthentication`). Avoids
  CSRF + cross-origin-cookie complexity, so the console can be hosted on any origin. Gate the whole
  app on `is_coach` (from `/api/v1/auth/me/`). *Alternative:* if you host it same-origin behind the
  existing Caddy (`/coach` path), use the browser session-cookie flavour instead — more secure token
  storage (httpOnly) at the cost of same-origin hosting. **Recommend app-token** for flexibility.
- **Hosting:** publish the static build behind the existing Caddy (a new `handle_path /coach/*` /
  file_server route, or a `coach.` subdomain). No new heavyweight container.
- **Distinct but consistent brand.** Reuse the TML Signal design tokens (gradient, per-domain
  accents) but a **denser, desktop-first, data-table-heavy** layout — this is a professional tool
  used at a desk, not a phone.

---

## Phase 0 — Foundations *(shell + auth + acting-client layer)*

**Goal:** a coach signs in and lands on an (empty) roster.

- [ ] SvelteKit project, Tailwind, design tokens ported from the athlete app; desktop-first shell
      (left rail: Roster · Check-ins · Templates · Settings).
- [ ] **Auth:** app-token login → store token → `is_coach` gate (non-coaches get a "not a coach"
      screen). Reuse the athlete app's auth patterns.
- [ ] **API layer:** a typed client with a global **acting-client context** (`setActingClient(id)`)
      that injects `X-Acting-Client` on every per-client call — port `$lib/api/acting.ts`.
- [ ] `/api/v1/coaching/clients/` wired; empty roster renders.

## Phase 1 — Roster command center *(triage)*

**Goal:** "who needs me today?" at a glance.

- [ ] **Roster grid:** one row/card per active client — name, current phase + week, bodyweight
      trend arrow, days since last check-in, adherence %, and an **alert badge** (see Phase 5).
      Sortable/filterable; default sort = *needs attention first*.
- [ ] **Invite / manage clients:** invite by email (`POST /coaching/invites/`), see pending/active,
      revoke (`/links/<id>/revoke/`), toggle prescription-edit permission (`/links/<id>/permission/`).
- [ ] **Client overview drawer:** `GET /coaching/clients/<id>/overview/` (composed dashboard +
      weekly check-in + body analysis) as a quick peek without leaving the roster.
- **Server (small):** enrich the roster brief with adherence + alert-count + "check-in/bloodwork
  due" so the grid doesn't need N follow-up calls (see [`BACKEND_CAPABILITIES.md`](BACKEND_CAPABILITIES.md)).

## Phase 2 — Client workspace *(read-only deep dive)*

**Goal:** everything about one client, coach-oriented, in one place.

Open a client → a workspace with domain sections, all read via `X-Acting-Client`:
- [ ] **Overview:** composition, adaptive TDEE, current prescriptions, recent activity.
- [ ] **Nutrition:** target vs logged adherence over time; adaptive-TDEE recommendation; macro/micro
      trends.
- [ ] **Training:** current program; performance — e1RM per lift, weekly volume per muscle, PRs, and
      session history.
- [ ] **Protocols:** active protocol; dose adherence; **concentration/release curves**; injection-site
      rotation.
- [ ] **Bloodwork:** results table with SI units/ranges, trends, derived (free-T, eGFR), and
      **out-of-range flags**.
- [ ] **Progress:** photo timeline + side-by-side compare; measurements; bodyweight EWMA.
- [ ] **Analysis:** body-analysis read (composition/insights); the parked deviation engine slots in
      here later.

## Phase 3 — Prescription tools *(the write side)*

**Goal:** change the plan, safely, from the coach's chair.

- [ ] **Nutrition target editor** → create+activate a `NutritionTarget` (calories/macros/fiber/water
      + optional micro min–max) for the client.
- [ ] **Training program builder** — reuse the extracted `ProgramBuilder.svelte`: days/slots/exercises/
      planned sets, activate (single-active invariant preserved server-side).
- [ ] **Protocol builder** — reuse `ProtocolBuilder.svelte`: compounds/supplements, cadence, timing
      slots, route.
- [ ] **Phase management** — create/activate a phase (bulk/cut/maintenance/peak) and add a
      **phase adjustment** that swaps program/target/protocol at a dated boundary (the periodization
      spine). This is the coach's highest-leverage action.
- All writes go to the existing prescription endpoints with `X-Acting-Client` (already authorized).

## Phase 4 — Check-in review workflow *(the weekly loop — the heart of coaching)*

**Goal:** an inbox of submitted check-ins; review each and respond with feedback + adjustments.

Grounded in how physique coaches actually work: weekly data → course-correct before momentum dies
(sources at end).

- [ ] **Check-in inbox:** clients with a submitted/ due weekly check-in, ordered by due/overdue.
- [ ] **Review view (single screen):** bodyweight trend + EWMA and **rate %/wk**; front/side/back
      **photo compare** vs last check-in; measurement deltas; wellbeing (energy/sleep/mood/soreness);
      training output + adherence; nutrition adherence vs target; dose adherence; any new bloodwork.
- [ ] **Respond in place:** write **feedback** (a comment) + apply an **adjustment** (new target /
      phase adjustment / program tweak) without leaving the screen; mark reviewed.
- **Server (new):** a lightweight **check-in feedback/comment** model + endpoint (backend "Stage 3"
  was scoped but not built) — see [`BACKEND_CAPABILITIES.md`](BACKEND_CAPABILITIES.md).

## Phase 5 — Safety & alerts monitor *(the enhanced-coaching differentiator)*

**Goal:** surface what a busy coach would otherwise miss — especially health risk.

- [ ] A rules feed per client + a roster-wide **alerts** panel: bloodwork out of range (hematocrit,
      lipids, ALT/AST, eGFR, estradiol), BP trend, **rapid bodyweight change**, low adherence,
      **overdue check-in / overdue bloodwork**. This is uniquely valuable for enhanced athletes and
      is *not* something generic coaching tools do.
- **Server (small):** an **alerts endpoint** that computes flags from existing data (thresholds
  server-side so both clients agree), or compute client-side v1 and move server-side when stable.

## Phase 6 — Templates & scale

**Goal:** stop rebuilding the same plan per client.

- [ ] Coach-owned **templates** for programs / protocols / nutrition targets; apply a template to a
      client (clone into their account via the acting-client write). Enables real caseload scale.
- **Server (optional):** template models, or v1 = clone from one of the coach's existing
  clients/own objects.

## Phase 7 — Polish, deploy, (optional) messaging

- [ ] Static build behind Caddy (new route) or `coach.` subdomain; smoke-test auth + a full
      review→prescribe loop against the live backend.
- [ ] Accessibility, keyboard-first navigation (coaches live on the keyboard), print/export a
      client report (reuse the existing check-in report PDF).
- [ ] *(Optional)* lightweight coach↔client messaging thread (backend Stage 3 extension).

---

## Sequencing rationale

0–1 prove auth + the roster (least surface, immediate value: see all clients). 2 makes one client
fully legible read-only. 3 unlocks changing the plan. **4 is the product** — the weekly review loop
is where coaching happens and where this tool earns its keep. 5 adds the safety layer that
justifies "enhanced-athlete coaching," 6 scales the caseload, 7 ships it. Each phase is usable on
its own; you could coach real clients after Phase 4.

## Cross-cutting

- **Design system:** desktop-dense variant of the TML Signal tokens; data tables, compact charts
  (reuse `LineChart` et al.), keyboard nav.
- **Sync/authority:** keep the split — *logged data device→server (backup), prescriptions
  server→device (pull)* — coherent; this app only writes prescriptions, so it fits the model.
- **Contract:** generate types from the backend OpenAPI (`/api/schema/`) like the other clients.

## Sources (coaching-platform + methodology research)

- [Trainerize vs TrueCoach vs Everfit (2026)](https://www.trainerize.com/blog/trainerize-vs-truecoach-vs-everfit-online-coaches/)
- [CoachRx feature comparison](https://www.coachrx.app/coachrx-comparison)
- [TrueCoach — tracking macros & calories for coaching](https://truecoach.co/blog/how-to-effectively-track-macros-and-calories-for-weight-loss-and-muscle-gain/)
- [Functional Bodybuilding — coaching](https://functional-bodybuilding.com/pages/coaching)
- [The Ripped Body — macro/adjustment methodology](https://rippedbody.com/macro-calculator/)
