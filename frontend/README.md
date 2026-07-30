# TML Signal — Coach Console

A **standalone web app for the coach**, purpose-built to manage clients on the TML Signal /
BBTracker platform. Not an extension of the athlete app — a coach-first command center:
a client roster with triage, a weekly check-in review workflow, and prescription tools for
phases, nutrition targets, training programs, and PED/supplement protocols.

It talks to the **same Django/DRF backend** on the TrueNAS home server that the iOS athlete app
uses. There is no new backend to build — the coaching API already exists (parked on the backend's
`coaching-stack` branch). This project is a new **frontend** plus a small set of additive server
features (check-in feedback, alerts, roster enrichment).

> **Status:** Phase 0 scaffolded — a SvelteKit + Svelte 5 + Tailwind v4 **static SPA** that
> builds (`npm i && npm run build`), with app-token auth, an `is_coach` guard, the coach shell
> (Roster · Check-ins · Templates · Settings), a roster wired to `/api/v1/coaching/clients/`, and a
> client workspace that exercises the `X-Acting-Client` mechanism. The coaching **API** it needs is
> now live on the BBTracker `backend-only` branch. Read [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md),
> [`docs/BACKEND_CAPABILITIES.md`](docs/BACKEND_CAPABILITIES.md), and [`docs/COACH_UX.md`](docs/COACH_UX.md).
>
> **Run it:** `cp .env.example .env` → `npm install` → `npm run dev` (the dev server proxies
> `/api` + `/_allauth` to the backend at `localhost:8000`).

## Why a separate app (not a tab in the athlete app)

The athlete app answers "what do I do today and did I do it?" A coach app answers a different
question: **"across all my clients, who needs my attention, and what should I change?"** That's a
triage + review + prescribe loop over *many* people, and it deserves its own information
architecture — a roster command center, a check-in inbox, side-by-side client history — rather
than the single-user tabs of the athlete app reused through a "view as client" lens.

## The moat

Mainstream coaching software (TrueCoach, Trainerize, CoachRx) covers training delivery, macros,
and messaging. **None** of them unify **training + nutrition + PEDs/bloodwork + periodization** in
one place. This platform already captures all of it per athlete. The Coach Console turns that into
the differentiator: a coach who can see a client's **hematocrit trend next to their testosterone
protocol, bodyweight rate, and training volume** — and prescribe against it — is doing something
no off-the-shelf tool supports. (Sources in the plan.)

## How it fits

```
                         ┌─────────────────────────────┐
   iOS athlete app ────► │  Django/DRF API (TrueNAS)    │ ◄──── Coach Console (this app)
   (local-first,         │  /api/v1/ + /_allauth/       │       (browser SPA, coach-only)
    backs up to server)  │  coaching app = access layer │
                         └─────────────────────────────┘
```

- **Athlete** logs on the iPhone; the device backs up to the server.
- **Coach** signs in here (an `is_coach` account), sees the roster, opens a client, reviews their
  check-in, and prescribes — every client read/write carries an `X-Acting-Client: <id>` header the
  backend authorizes (reads for any active link; writes only for prescription endpoints).

The one architectural knot to design carefully — reconciling the athlete app's **local-first**
model with **server-authored prescriptions** — is covered in
[`docs/BACKEND_CAPABILITIES.md` §Sync & authority](docs/BACKEND_CAPABILITIES.md).

## Stack (proposed)

**SvelteKit + Svelte 5 + Tailwind v4**, same as the athlete web app — to reuse the design system,
the API-client patterns, the acting-client header layer (`$lib/api/acting.ts`), and the already-built
`ProgramBuilder` / `ProtocolBuilder` from `coaching-stack`. Built as a **static SPA** (adapter-static),
auth via allauth's headless **app token** (`X-Session-Token`, same as iOS — no CSRF/CORS friction),
hosted as static files behind the existing Caddy. Detail + alternatives in the plan.
