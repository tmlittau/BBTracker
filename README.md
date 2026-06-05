# BBTracker

A unified, privacy-first **self-coaching** web app for bodybuilding — combining nutrition,
training, supplements, medications/PEDs, and a progress diary into one timeline-linked
platform (instead of 4–5 separate apps).

- **Frontend:** Svelte 5 / SvelteKit (TypeScript, Tailwind, PWA)
- **Backend:** Python / Django + Django REST Framework, PostgreSQL
- **Media:** private object storage (signed URLs)

The differentiator is **integration**: a master *Phases/periodization timeline* and an
auto-generated *weekly Check-in* that aggregate everything a coach would review.

> **Disclaimer:** BBTracker is a personal tracking and journaling tool. It is **not** a
> medical device and does **not** provide medical advice. It does not recommend, prescribe,
> or endorse any substance, dose, or protocol — you enter your own data. Use under
> appropriate professional medical supervision and monitor your health with regular bloodwork.

## Documentation

See **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** for the full scope, competitive
analysis, architecture, data model, API design, security/privacy plan, and phased roadmap.

## Status

**Complete and verified — all five domains plus the self-coaching layer that unifies them.**
Foundation (accounts, **TOTP 2FA**, DRF + OpenAPI → typed SvelteKit client, SSR auth guard) →
**Training** → **Nutrition** (with Open Food Facts barcode import) → **Supplements & Medications**
→ **Progress Diary** → **Self-coaching layer** (periodization timeline + weekly check-in).

**Iteration 2 (MVP feedback).** In-context creation everywhere — a reusable `<Modal>` plus
create-modals for exercises/compounds/supplements, surfaced inside the builders — and richer
visuals. **Training:** edit planned sets inline, drag-reorder exercises, per-set rest that **counts
down** in the live logger, and **start a workout from a program day** (pre-loaded sets turn green as
you log; finishing early prompts to keep only completed sets). **Nutrition:** dynamic per-day
**meals** (rename / reorder / delete), a macro⇄micro toggle on the headline block, per-macro colours,
and micro fill bars. **Protocols:** sub-tabs, an active-only main page with quick-log, day-of-week +
time-of-day **scheduling**, deletable supplement-nutrient rows, and a reworked **bloodwork** view
(bulk panel entry, a tabular %-trend matrix with out-of-range colouring, and a per-marker chart).
**Diary:** more poses (relaxed-from-every-side, most-muscular, classic), required bodyweight, a
bodyweight plot with a 7-day-average overlay, and themed ⚡/😴/🙂/🔥 rating symbols. **Phases:** a
phase now holds a dated **adjustment** timeline (target/program/protocol evolve over time); the
dashboard resolves whichever adjustment is in force today.

**Iteration 2 — feedback follow-up.** Sub-tab navigation across every tab (Training / Nutrition /
Diary now match Protocols) with per-domain accent colours throughout the dark UI; the Training tab's
main view shows only the **active program** with a one-tap **Start** per training day (full list under
*Programs*); custom foods can be created **on the fly** while adding to a meal, and foods/drinks can
be measured in **g or ml**; and the bloodwork catalogue now covers a full **~57-marker panel** (CBC,
iron, liver, lipids incl. ApoA/B, glucose/HbA1c, renal, electrolytes, vitamins, thyroid, and the full
sex-hormone panel) with sex-specific reference ranges.

**Self-coaching layer** (`apps/core/`) — the integration that makes this one app, not five:

- **`Phase` + adjustment timeline** — a phase ("Off-season bulk", "Prep", "Cruise") spans a date
  range; a dated **`PhaseAdjustment`** timeline within it carries the nutrition target, program, and
  protocol in force from each `effective_date` (cross-app `SET_NULL` FKs), so the prescription can
  evolve mid-phase. Everything logged resolves to a phase **by date**, and the dashboard surfaces the
  adjustment in force today.
- **Real dashboard "Today"** (`/api/v1/dashboard/today/`) — aggregates the current phase +
  nutrition headline vs target + today's workout (with PRs) + today's doses, across all domains.
- **Weekly check-in report** (`/api/v1/checkin/weekly/`) — the self-coaching payload: bodyweight
  trend, training output (sessions/PRs/volume + top muscles), nutrition adherence, dose count,
  subjective wellbeing averages, photos taken, and latest bloodwork over the trailing 7 days.
- **UI** — `(app)/phases/` timeline editor, a rewritten `(app)/dashboard/` with live domain
  tiles, and an `(app)/check-in/` weekly report. Core services use function-local cross-app
  imports so `core` has no hard dependency on the domain apps.

**Phase 4 — Progress Diary** (`apps/diary/`): `Pose` (13 mandatory + relaxed/most-muscular/classic poses), `CheckIn` (dated,
one-per-day: bodyweight + five 1–5 subjective scores), `ProgressPhoto` (per-pose; binary in
**MinIO** via S3/boto3, EXIF-stripped + thumbnailed by Pillow, streamed back through the
owner-scoped API — never public URLs). UI: check-in feed, pose-filtered gallery, uploader with a
**ghost overlay** of your last same-pose photo, two-photo comparison.

Earlier phases: **Training** (`apps/training/`), **Nutrition** (`apps/nutrition/`, with OFF
barcode import), **Supplements & Medications** (`apps/protocols/` — compound library with
half-life/ester constants, dose logging with an interactive SVG body-map injection-site picker,
protocol adherence, bloodwork trends with sex-specific reference flags, and a supplement →
nutrition micronutrient feed). A shared `apps/core/viewsets.OwnerScopedViewSet` backs
owner-isolation across all domains.

**Account settings.** `GET`/`PATCH /api/v1/auth/me/` reads and updates the current user plus the
nested `Profile` (sex, date of birth, height, units, timezone); email is read-only. A **Settings**
page (`(app)/settings/`, linked from the header email) edits these. Setting **sex** unlocks
sex-specific bloodwork reference ranges (e.g. Total Testosterone) in the protocols trend flags,
which stay unflagged while sex is "unspecified".

> **Disclaimer:** the medications/PEDs module is a personal **tracking/journaling** tool, not a
> medical device. It records *your own* data and contains only factual pharmacokinetic reference
> constants — it does not recommend, prescribe, or endorse any substance, dose, or protocol.

**Verification:** backend **175 tests** pass (sqlite via `backend/.venv` or in-container Postgres),
ruff clean; frontend **type-check (0 errors) + 32 unit tests** pass; **Playwright** drives the real
UI for auth, training, nutrition, protocols, settings, diary, and coaching (**9/9**, run under
Node ≥ 20 against the live stack); and browser-equivalent cookie-jar scripts pass — `verify_auth.py`
12/12, `verify_training.py` 30/30, `verify_nutrition.py` 32/32 (incl. a live OFF barcode import),
`verify_protocols.py` 32/32, `verify_profile.py` 14/14, `verify_diary.py` 22/22 (real MinIO
upload→stream round-trip), `verify_selfcoaching.py` 24/24 (phase adjustments + cross-domain
dashboard + weekly rollup). The
original implementation plan is fully delivered; see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
§12 for post-v1 ideas (PWA offline gym logging, web-push reminders, native HealthKit sync).

### Seeding reference data

```bash
docker compose exec backend python manage.py seed_training    # 17 muscles, 24 exercises
docker compose exec backend python manage.py seed_nutrition   # 26 nutrients, 12 foods
docker compose exec backend python manage.py seed_protocols   # 24 compounds, 12 sites, 22 markers
docker compose exec backend python manage.py seed_diary        # 8 mandatory poses
```

### Running browser E2E (Playwright)

Playwright 1.60 needs Node ≥ 18.19; this repo's host default is 18.17. Run it under a Node ≥ 20
install (adjust the path to whatever `nvm`/Volta version you have), with the stack up and
reference data seeded:

```bash
cd frontend
nvm use 20   # or otherwise put Node ≥ 18.19 first on PATH
npx playwright test
```

> Specs live in `frontend/tests/e2e/` (auth, training, nutrition, protocols, settings, diary,
> coaching) — **9 tests, all passing** against the running stack under Node ≥ 20. The equivalent
> flows are also covered headlessly by the `scripts/verify_*.py` checks.

### End-to-end verification scripts

```bash
/opt/anaconda3/bin/python scripts/verify_auth.py        # auth + 2FA flow (12 checks)
/opt/anaconda3/bin/python scripts/verify_training.py    # training: start-from-day, countdown rest, reorder (30 checks)
/opt/anaconda3/bin/python scripts/verify_nutrition.py   # nutrition: dynamic meals + ml unit (32 checks, incl. live OFF import)
/opt/anaconda3/bin/python scripts/verify_protocols.py   # protocols: scheduling + bloodwork matrix (32 checks)
/opt/anaconda3/bin/python scripts/verify_profile.py     # profile edit + bloodwork flagging (14 checks)
/opt/anaconda3/bin/python scripts/verify_diary.py       # progress diary: MinIO photo round-trip (22 checks)
/opt/anaconda3/bin/python scripts/verify_selfcoaching.py # phase adjustments + dashboard + weekly check-in (24 checks)
```

## Running locally

```bash
cp .env.example .env
docker compose up --build      # db, redis, minio, backend (:8000), frontend (:5173)
```

Open <http://localhost:5173>, register, enroll TOTP, land on the dashboard. API docs:
<http://localhost:8000/api/docs/>. Admin user:
`docker compose exec backend python manage.py createsuperuser`.

**Regenerate the typed API client** after backend schema changes (backend must be running):

```bash
cd frontend && npm run gen:api      # writes src/lib/api/schema.d.ts
```

### Notes / gotchas

- **Email verification & 2FA.** Dev uses `ACCOUNT_EMAIL_VERIFICATION="none"`, and a
  `user_signed_up` signal marks the email verified so TOTP can be enrolled immediately.
  **Before production**, require real email verification and gate that signal on `DEBUG`
  (see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) §10).
- **Docker BuildKit hang.** If `docker compose build` stalls at "load metadata", BuildKit is
  unhappy on this machine; build the backend image with the legacy builder instead:
  `DOCKER_BUILDKIT=0 docker build -t bbtracker-backend ./backend`.
- **Tailwind v4 native binary.** Platform `@tailwindcss/oxide-*` binaries are pinned in
  `frontend/package.json` `optionalDependencies` (lockstep with `tailwindcss`) to dodge the
  npm optional-deps bug; install with `npm ci`.
- **Frontend deps in Docker.** The `frontend` service mounts an anonymous `node_modules` volume
  baked at image build, so a new dependency (e.g. `svelte-dnd-action` for drag-reorder) needs either
  `docker compose build frontend` or `docker compose exec frontend npm install` + a restart before
  the dev server (and Playwright) can see it.

### Fast backend iteration (no Docker)

A virtualenv at `backend/.venv` (Python 3.12) runs tests quickly against SQLite:

```bash
cd backend
DATABASE_URL='sqlite:////tmp/bbtracker_dev.sqlite3' DJANGO_SECRET_KEY=dev ./.venv/bin/python -m pytest
```
