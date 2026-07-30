# Backend capabilities for the Coach Console

What the Django/DRF backend already provides, the per-client data available, the one hard
architectural knot (sync & authority), and the small additive server work the console needs.

---

## 1. The coaching API already exists (parked on `coaching-stack`)

A full `apps/coaching` was built and tested, then parked (unmerged). It is the whole access layer.

### `CoachClientLink` (the relationship)
`coach`, `client`, `status ∈ {pending, active, declined, revoked}`, `can_edit_prescriptions`
(bool, client-controlled), timestamps, `unique(coach, client)`. Client-consent gated: a coach
invites, the client accepts, and can revoke or toggle edit access at any time.

### The `resolve_effective_owner` chokepoint (the security core)
Every owner-scoped view reads its scope from `effective_owner` instead of `request.user`. A coach
targets a client with an **`X-Acting-Client: <user_id>`** header:

- **Reads (safe methods):** allowed for any **active** link.
- **Writes (unsafe):** allowed **only** on views that opt in (`prescription_write = True`) **and**
  only when the link grants `can_edit_prescriptions`. Every other write resolves to `request.user`.
- A header present but not authorized is a hard **403** — it never silently falls back to the
  coach's own data. Missing a read endpoint fails closed (coach sees their own empty data, never
  another client's).

**Consequence for this app:** a coach can never see a client they aren't linked to, and can never
write a client's *logged* data — only prescriptions. The console inherits this for free.

### `/api/v1/coaching/` endpoints
| Method + path | Purpose |
|---|---|
| `GET clients/` | The coach's active clients (brief: name, current phase, last check-in, weight). |
| `GET clients/<id>/overview/` | Composed snapshot = `dashboard_today` + `weekly_checkin` + `body_analysis`. |
| `GET/POST invites/` | List sent/received invites; invite a client by **email** (must be an existing account). |
| `POST invites/<id>/respond/` | Client accepts/declines. |
| `POST links/<id>/revoke/` | Either party revokes. |
| `POST links/<id>/permission/` | Client toggles `can_edit_prescriptions`. |

### What a coach may **write** for a client (`prescription_write = True` viewsets)
Confirmed on `coaching-stack`:
- **Periodization:** `Phase`, `PhaseAdjustment` (`apps/core`).
- **Nutrition:** `NutritionTarget`, `NutrientTarget` (calorie/macro/fiber/water + micro min–max).
- **Training:** `Program` + days + slots + planned sets (the full builder).
- **Protocols:** `Protocol` + items (compounds/supplements, cadence, timing, route).

Everything else (logged workouts, food diary, dose logs, check-ins, bloodwork results) is
**read-only** to the coach. That's the correct coaching split: **coach prescribes, athlete logs.**

### Reusable frontend already on `coaching-stack`
`$lib/api/acting.ts` (the acting-client header context), `$lib/coaching/api.ts` +
`clients.ts`, and the extracted `ProgramBuilder.svelte` / `ProtocolBuilder.svelte`. Lift these into
the console rather than rewriting.

> **Prerequisite:** none of this is on the deployed backend yet. `coaching-stack` must be merged +
> deployed first. (It predates the recent iOS/local-first and backend-only changes, so expect a
> rebase against current `main` before merge.)

---

## 2. Per-client data available (the moat)

Read via the normal domain endpoints with `X-Acting-Client`. This is what no off-the-shelf coaching
tool has in one place:

| Domain | Endpoints (read) | What the coach sees |
|--------|------------------|---------------------|
| Periodization | `/api/v1/phases/`, dashboard | bulk/cut/maintenance/peak timeline + dated adjustments |
| Nutrition | `/nutrition/summary/`, targets, diary | target vs logged adherence, macros/micros/water, adaptive TDEE |
| Training | `/training/…` sessions, logged sets | e1RM per lift, weekly volume per muscle, PRs, history |
| Protocols | `/protocols/…` doses, release-curve | dose adherence, **concentration/release curves**, site rotation |
| Bloodwork | `/protocols/blood…`, matrix | SI results + ranges, trends, derived (free-T, eGFR), flags |
| Body / analysis | `/analysis/body/`, measurements | composition, BMR/adaptive TDEE, insights, waist/arm/etc. |
| Diary | `/diary/…` photos, poses | progress photos (front/side/back), check-ins |
| Subjective | weekly check-in | energy/sleep/mood/motivation/soreness, BP, resting pulse |

The cross-domain view — e.g. **hematocrit trend beside the testosterone protocol beside bodyweight
rate beside training volume** — is the console's reason to exist.

---

## 3. Sync & authority — the one hard problem to design

The athlete app is now **local-first / device-authoritative**: the athlete logs on the iPhone and
the device **backs up** structured snapshots to the server (`PUT /api/v1/sync/backup/`, projected
into the relational tables via `apps/core/replica`). Coaching, however, is **server-authored**: the
coach writes prescriptions on the server. These two must reconcile, or the loop is broken.

**Two questions to answer before Phase 2/3:**

1. **Do coach reads see real data?** Verify the device backup **projects the full structured
   snapshot into the relational tables** the coaching read endpoints use (the health aggregates
   already do via `apply_replica_health`; confirm training/nutrition/protocols/diary do too). If a
   backup is an opaque blob, coach reads are empty until this projection exists.

2. **How do coach prescriptions reach the device?** The recommended model is a **split authority**:
   - **Logged data** (workouts, food, doses, check-ins) — *device-authoritative*: device writes →
     backs up → coach reads.
   - **Prescriptions** (phases, targets, programs, protocols) — *server-authoritative*: coach writes
     on the server → the **device pulls** them (on bootstrap/refresh) and treats them as
     read-mostly "assigned by my coach," not part of its local-authoritative set.

   This split maps cleanly onto the existing access rules (coach may write *only* prescriptions;
   athlete logs *only* their own data) and onto the athlete app's own model (it already distinguishes
   assigned plans from logged data). The concrete work is on the **iOS app** (pull + surface
   coach-assigned prescriptions, and reflect a prescription changing mid-cycle), not on this console.
   The console just writes prescriptions to the server as the coaching endpoints already allow.

Flag this to the athlete-app track; the console can be built against the server in parallel, but the
*athlete-visible* loop only closes once the device pulls coach prescriptions.

---

## 4. Small additive server work the console wants

All additive; land as normal PRs against the backend. None are blockers for Phases 0–3.

1. **Roster brief enrichment** *(small).* Extend `GET /coaching/clients/` with per-client
   adherence %, alert count, and "check-in due / bloodwork due" so the roster grid needs no N+1
   follow-up calls.
2. **Check-in feedback / comments** *(new, Phase 4).* A `CheckInComment` (or coach-feedback) model +
   endpoint so the coach's weekly response is stored and the athlete sees it. This is the backend's
   scoped-but-unbuilt "Stage 3."
3. **Alerts endpoint** *(small, Phase 5).* Compute per-client flags server-side (bloodwork out of
   range, BP trend, bodyweight velocity, low adherence, overdue check-in/bloodwork) so thresholds
   are shared and the roster can badge them. v1 may be client-side, then move server-side.
4. **Coaching templates** *(optional, Phase 6).* Coach-owned program/protocol/target templates +
   an "apply to client" clone. v1 can clone from the coach's existing objects with no new model.
5. *(Optional)* **Coach-entered bloodwork.** Today bloodwork is athlete-logged (read-only to the
   coach). If you want to enter a client's labs yourself, add bloodwork to the prescription-write
   scope or a dedicated coach-entry endpoint.

---

## 5. Auth & hosting (console-specific)

- **Auth:** allauth headless **app token** — `POST /_allauth/app/v1/auth/login` → `meta.session_token`
  → send `X-Session-Token` on every call. Already authorized by `XSessionTokenAuthentication` on
  `main`. Gate the app on `is_coach` from `/api/v1/auth/me/`. No CSRF, no CORS constraints, so the
  static SPA can live on any origin.
- **Hosting:** publish the static build behind the existing Caddy (add a `/coach/*` file-server
  route or a `coach.` subdomain). No SSR node container — keeps the "backend-only" prod lean.
- **CORS note:** app-token auth needs no CORS (no browser Origin trust). If you instead choose
  same-origin session-cookie auth, host the console on the same origin as the API.
