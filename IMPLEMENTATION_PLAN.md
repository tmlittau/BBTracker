# BBTracker — Implementation Plan

> A unified, self-coaching web app for bodybuilding: nutrition, training, supplements,
> medications/PEDs, and a progress diary — combining what is normally 4–5 separate apps
> into one timeline-linked platform.

**Stack:** Svelte 5 / SvelteKit (frontend) · Python / Django + Django REST Framework (backend API) · PostgreSQL · object storage for media.

**Status:** Planning. This document is the source of truth for scope, architecture, data model, and the build roadmap.

---

## 1. Vision & Differentiator

There are excellent point solutions for each bodybuilding concern, but they don't talk to
each other. A real coach reviews *everything together* — weight trend vs. calories vs.
training volume vs. what compounds you're running vs. how you look and feel — and adjusts.

**BBTracker's differentiator is integration, not any single feature.** Two unifying concepts
make it a self-coaching tool rather than five trackers in a trench coat:

1. **Phases / Periodization timeline** — a master timeline of *Phases* (e.g. "Off-season
   bulk", "Prep", "Cruise/TRT", "Blast", "Mini-cut"). Each phase links a nutrition target
   set, a training program, and a medication/supplement protocol, with a start/end date.
   Everything else (logs, photos, bloodwork, PRs) timestamps onto this timeline so cause and
   effect become visible.

2. **The weekly Check-in** — an auto-generated review that aggregates everything a coach
   would look at (weight trend, training volume & PRs, nutrition adherence, protocol
   adherence, subjective scores, latest photos, due bloodwork) into one screen and an
   exportable report. This is the "self-coaching" payload.

Everything in the roadmap serves these two ideas.

---

## 2. Competitive Analysis — what to borrow

| App | Domain | What it does best (borrow this) | Gap we fill |
|---|---|---|---|
| **Strong** | Training | Fast in-gym logging; routine templates; set types (warmup/normal/drop/failure); supersets; rest timer; plate calculator; RPE; e1RM & PR detection; clean history/charts | Siloed from nutrition/meds; no periodization/mesocycle planning |
| **Hevy** | Training | Similar to Strong + routine folders, exercise instructions/media, good UX | Same silo problem |
| **RP Hypertrophy** | Training (periodization) | Mesocycle planning, volume landmarks (MEV/MAV/MRV) per muscle, RIR auto-regulation, automatic set/load progression, programmed deloads | Subscription, training-only |
| **Cronometer** | Nutrition | Deep **micronutrient** tracking (80+ nutrients), authoritative food data, barcode scan, custom foods/recipes, biometrics, targets, nutrient-density focus | Doesn't integrate supplement/med micros or training context |
| **MacroFactor** | Nutrition | Dynamic TDEE/expenditure from weight-trend + intake math; adaptive macro targets; trend-weight smoothing; very fast logging | Nutrition-only |
| **MyFitnessPal** | Nutrition | Huge crowd food DB, barcode | Data quality, ads; nutrition-only |
| **Apple Health — Medications** | Meds/Supps | Add meds & supplements, dose schedules, reminders, log taken/skipped, **critical interaction warnings**, supports supplements too | No PED/anabolic modeling (esters, half-lives, injection-site rotation, cycle/PCT), no bloodwork-centric view; iOS-only |
| **Dedicated cycle trackers** | PEDs | Compound library with esters/half-lives, dose schedules by cadence (ED/EOD/E3D/2×wk), injection-site rotation, active-concentration curves, bloodwork & side-effect logs, PCT planning | Usually crude UX, no nutrition/training integration, privacy concerns |
| **Progress-photo apps** | Diary | Pose categories, side-by-side/over-time comparison, private galleries, timelines | Not tied to the rest of the data |

**Design takeaways baked into the plan**

- *The market is converging on exactly this thesis.* MacroFactor (nutrition-only) launched a **Workouts** companion in early 2026; Strong/Hevy keep adding analytics; cycle-tracker apps now bolt on bloodwork. Nobody has unified all five domains on one timeline — that's the opening.
- *Logging speed wins.* The training and food loggers must be as fast as Strong/MacroFactor — large tap targets, "repeat last", recents/favourites, keyboard-friendly on desktop, works offline in the gym.
- *Micronutrients are first-class*, Cronometer-style — and **supplements/meds feed the same daily micro totals**.
- *PEDs deserve real modeling*, not a generic "medication" row: esters, half-lives, routes, injection-site rotation, and a bloodwork-first monitoring view (harm reduction).
- *Periodization* (RP-style mesocycles, volume landmarks, RIR/progression) is what elevates training above a logbook.
- *Privacy is a feature*, not an afterthought (see §10).

---

## 3. Product Scope — Modules & Features

Legend: **[MVP]** ship first · **[v1]** core release · **[later]** post-v1.

### 3.0 Foundation (cross-module)
- **[MVP]** Accounts, profile (sex, DOB, height, unit prefs, timezone), secure auth + 2FA.
- **[MVP]** **Phases/timeline** entity (see §1).
- **[MVP]** Unified **Dashboard** ("Today"): today's nutrition vs target, scheduled
  supplements/doses, planned workout, quick-log shortcuts, current phase.
- **[v1]** **Weekly Check-in** report (aggregation + PDF/share export).
- **[v1]** Body metrics: weight log (with trend smoothing), body-fat %, tape measurements.
- **[later]** Reminders/notifications (web push), data export/import, account deletion.

### 3.1 Nutrition (Cronometer + MacroFactor inspired)
- **[MVP]** Food database: search; **custom foods**; per-serving macros + full micros.
- **[MVP]** Food diary: log by meal (breakfast/lunch/dinner/snacks), quantities & serving units; "copy yesterday", recents, favourites.
- **[MVP]** Daily targets: calories, protein/carb/fat (+ fiber); progress rings/bars.
- **[v1]** Micronutrient targets & breakdown (vitamins/minerals); nutrient density view.
- **[v1]** Recipes (composed of foods) and meals (saved groups).
- **[v1]** External food data: **Open Food Facts** (barcode) + **USDA FoodData Central** import, cached as local foods.
- **[v1]** **Supplement micros roll into daily totals** (integration with §3.3).
- **[later]** Adaptive targets (MacroFactor-style TDEE estimate from weight-trend + intake), per-day-type targets (training vs rest), water/hydration, barcode scan via camera (PWA).

### 3.2 Training (Strong + RP inspired)
Hierarchy exactly as requested: **Program/Split → Training Day → Exercise → Sets**.
- **[MVP]** Exercise library: name, primary/secondary muscles, equipment, category, instructions/notes; user-custom exercises.
- **[MVP]** Build **Programs** (e.g. "Push/Pull/Legs") → **Days** (e.g. "Push") → ordered **Exercise slots** → **planned sets** with **set types** (warmup, working/regular, drop, rest-pause, myo-rep, cluster, AMRAP, back-off, top-set, failure) and targets (reps, weight, %1RM, RPE/RIR, tempo, rest).
- **[MVP]** **Workout logging**: start a session from a Day (or freeform), log actual sets (reps/weight/RPE/type/done), rest timer, plate calculator, "repeat last session", notes.
- **[MVP]** History; per-exercise progression charts; **e1RM** (Epley/Brzycki) & **PR detection**.
- **[v1]** Supersets/giant sets (set grouping); per-muscle **weekly volume** (working-set counts & tonnage).
- **[v1]** **Mesocycle** support: weeks, programmed progression (linear / double-progression / RP-style RIR auto-regulation), deload weeks.
- **[later]** Volume landmarks (MEV/MAV/MRV) per muscle with guidance; warmup-set calculator; exercise media/video; 1RM calculator tools.

### 3.3 Supplements (Apple Health + Cronometer inspired)
- **[MVP]** Supplement catalog: name, brand, form (capsule/powder/liquid), serving size, **micronutrient content** (links to the nutrient model so it can feed §3.1), target benefits/tags, notes.
- **[MVP]** Schedules: dose, timing (e.g. with breakfast / pre-workout / before bed), cadence (daily, X×/week, cyclical on/off).
- **[MVP]** Daily supplement log (taken/skipped/time).
- **[v1]** Roll micros into daily nutrition totals; adherence stats.
- **[later]** Reminders; cost/inventory tracking ("X servings left"); stack templates.

### 3.4 Medications & Performance Enhancers (cycle-tracker + Apple Health inspired)
> Personal tracking & harm-reduction tool. **Not medical advice** (see §10). Covers
> pharmaceutical ancillaries (e.g. Telmisartan, Isotretinoin, AIs) *and* performance
> enhancers (anabolics, peptides).
- **[MVP]** Compound library: name, class (AAS, peptide, SARM, AI, SERM, ancillary, prescription, other), default unit (mg/mcg/IU), route (oral/subQ/IM/topical), **ester** & **half-life** (for injectables/active-curve modeling), notes.
- **[MVP]** **Protocols**: a named plan grouping compounds over a date range (cycle / cruise / TRT / blast / ancillary regimen), with per-compound **dose schedules** (amount, unit, cadence ED/EOD/E3D/2×wk/weekly, route, time, start/end, optional titration steps).
- **[MVP]** **Dose log**: actual administrations — datetime, compound, dose, route, **injection site**, notes, side-effects. Site selection via an **interactive SVG body map** with **recency colouring** (green = rested, amber = recent, red = needs recovery) and **next-site suggestion** based on rotation history (pattern proven by apps like Dosafy/CycleVitals).
- **[v1]** **Bloodwork / lab results**: marker, value, unit, reference range, date; trend charts with reference bands for the markers these protocols actually move — **Total T, Free T, SHBG, Estradiol, LH/FSH, PSA, Hemoglobin/Hematocrit, lipid panel, ALT/AST, eGFR** — plus a **blood-pressure log** (Telmisartan use-case). This is the monitoring backbone.
- **[v1]** **Vial / inventory tracking** (doses remaining per vial/bottle, "reorder" threshold) and concentration (mg/ml) for accurate volume math.
- **[v1]** Active-concentration curve visualization from dose history + half-life **and ester weight**; adherence; side-effect timeline; **correlation overlay** of protocol changes vs. bloodwork/BP trends.
- **[later]** PCT planner; reminders; "due bloodwork" prompts surfaced on the dashboard/check-in; basic interaction flags (clearly labelled informational, not advice).

### 3.5 Progress Diary (progress-photo apps inspired)
- **[MVP]** **Progress photos** by **pose type** (front relaxed, front double biceps, side chest, back double biceps, back lat spread, side triceps, abs & thighs, most muscular, plus custom), with date and optional bodyweight at capture.
- **[MVP]** Journal entries: free-text notes + structured **check-in scores** (mood/headspace, energy, sleep quality, hunger, libido, pumps, soreness — configurable).
- **[v1]** **Comparison view**: same pose across two dates / over time, side-by-side and slider.
- **[v1]** Photos & check-ins feed the weekly Check-in report.
- **[v1]** **Consistency helper** (the #1 thing that makes progress photos usable): a faint **ghost/overlay of the previous photo for the same pose** while capturing, so framing/angle/distance match; plus a same-time-of-day, fasted, morning reminder.
- **[later]** Optional on-device face/background blur for privacy before upload.

### 3.6 The integration layer (the actual product)
- **[v1]** **Dashboard "Today"** pulling from every module.
- **[v1]** **Weekly Check-in** aggregation + export (PDF/JSON) to share with a doctor/coach.
- **[later]** **Correlations / overlays**: one timeline charting weight, training volume, calories, and active compounds together; phase annotations.

---

## 4. System Architecture

```
┌────────────────────────┐        HTTPS / JSON (OpenAPI)        ┌───────────────────────────┐
│  SvelteKit (Svelte 5)  │  ───────────────────────────────▶   │   Django + DRF (API)      │
│  - SSR + CSR           │                                       │  - Auth (session+2FA/JWT) │
│  - Runes state         │  ◀───────────────────────────────    │  - DRF viewsets/serializers│
│  - PWA / offline queue │        signed media URLs              │  - drf-spectacular (schema)│
│  - Generated TS client │                                       │  - Celery tasks            │
└───────────┬────────────┘                                       └─────────┬─────────────────┘
            │                                                               │
            │ static assets / SSR (Node adapter)                            │
            ▼                                                               ▼
     Caddy / nginx (TLS, reverse proxy)                       ┌────────────┴───────────┐
                                                              │ PostgreSQL │ Redis │ Object store │
                                                              │  (data)    │(broker│ (S3/R2/MinIO │
                                                              │            │ +cache)│  private)    │
                                                              └────────────┴───────┴──────────────┘
```

**Key decisions**

- **API style:** REST via DRF, documented with **drf-spectacular** (OpenAPI 3). The frontend
  client is **generated** from that schema (typed end-to-end). Avoids hand-written clients drifting.
- **Auth (recommended):** **HttpOnly session cookies + CSRF**, with **TOTP 2FA**. SvelteKit
  SSR can proxy/forward cookies; simplest and most secure for a single-/few-user privacy-first
  app. *Alternative:* JWT (`djangorestframework-simplejwt`) if you later want a fully
  decoupled SPA or native clients. Decision recorded in §15.
- **Media:** progress photos & any sensitive files in a **private** bucket (S3 / Cloudflare R2 /
  self-host MinIO), served via **short-lived signed URLs**, encrypted at rest. Never public.
- **Background jobs:** **Celery + Redis** (reminders, web-push, food-DB sync, report/PDF
  generation). Lighter alternative: Huey or `django-q2` if you want to skip Celery early.
- **Integrations:** Open Food Facts (barcode/food), USDA FoodData Central (nutrient data).
  Apple Health/HealthKit is **not directly reachable from a web app** — see §15 (PWA-first;
  optional Capacitor wrapper later for HealthKit + camera + native push).

---

## 5. Tech Stack & Key Libraries

**Backend**
- Python 3.12+, Django 5.x, Django REST Framework
- PostgreSQL 16 (JSONB available for flexible/extra fields)
- `drf-spectacular` (OpenAPI schema) · `django-filter` (filtering) · `django-cors-headers`
- Auth: Django sessions + `django-otp`/`django-two-factor-auth` (2FA); **or** `djangorestframework-simplejwt`
- Celery + Redis · `django-storages` + `boto3` (S3-compatible media)
- `django-environ` (config) · `django-axes` (brute-force lockout) · `pydantic`/serializers for validation
- Tests: `pytest`, `pytest-django`, `factory_boy`, DRF `APIClient`
- Lint/format: `ruff`, `black`, `mypy`

**Frontend**
- SvelteKit + **Svelte 5 (runes: `$state`/`$derived`/`$effect`, snippets)** + TypeScript
- **Tailwind CSS v4** + accessible primitives (**Bits UI / shadcn-svelte / melt**)
- Charts: **LayerChart** (Svelte-native) for most; **uPlot** for dense time-series; (Chart.js/ECharts as fallback)
- Forms + validation: **sveltekit-superforms** + **zod**
- Server-state/caching + offline: **@tanstack/svelte-query**; **Dexie/IndexedDB** for the offline log queue
- API client: **openapi-typescript** + generated typed client from the DRF schema
- PWA/offline: **@vite-pwa/sveltekit** (service worker, installable, offline gym logging)
- Tests: **Vitest** + Testing Library; **Playwright** (E2E)

**Tooling/infra**
- Monorepo, Docker + docker-compose (Postgres, Redis, MinIO, backend, frontend)
- CI: GitHub Actions (lint, type-check, test, build, schema-drift check)
- Reverse proxy/TLS: Caddy (auto-HTTPS) or nginx + Let's Encrypt

---

## 6. Data Model

Conventions: every record has `id`, `created_at`, `updated_at`, and (where user-owned)
`owner` (FK→User). Enums shown as `{...}`. "→" = ForeignKey, "⇄" = M2M.

### Accounts & Core
- **User** (Django auth) — email/username, password, 2FA devices.
- **Profile** → User — sex, date_of_birth, height, unit_system `{metric,imperial}`, timezone, goal notes.
- **Phase** → User — name, type `{bulk,cut,maintain,recomp,prep,cruise,blast,trt,other}`, start_date, end_date(null=ongoing), notes; *optional* links: → NutritionTarget, → Program, → Protocol. **This is the timeline spine.**
- **BodyMetric** → User — date, weight, body_fat_pct, plus a flexible set of **Measurement** rows (site `{chest,waist,hips,arm_l,arm_r,thigh_l,…}`, value).
- **Tag**, **Attachment**, and an **AuditLog** (generic, for "tracking changes") shared across modules.

### Nutrition
- **Nutrient** — canonical list (name, category `{macro,vitamin,mineral,other}`, default_unit, optional RDA). Seeded once.
- **Food** → owner(null=global/imported) — name, brand, source `{custom,off,usda}`, source_id, barcode, default_serving; flags `is_verified`.
- **ServingSize** → Food — label (e.g. "1 scoop", "100 g"), grams.
- **FoodNutrient** → Food, → Nutrient — amount per 100 g (full macro+micro profile).
- **Recipe** → owner — name, servings; **RecipeItem** → Recipe, → Food, quantity.
- **DiaryEntry** → owner — date, meal `{breakfast,lunch,dinner,snack,…}`, → Food *or* → Recipe, quantity, serving.
- **NutritionTarget** → owner — name, kcal, protein/carb/fat/fiber, optional per-micro targets (via **NutrientTarget** rows), optional day_type `{training,rest,any}`. Linked from Phase.

### Training
- **Exercise** → owner(null=global) — name, category `{barbell,dumbbell,machine,cable,bodyweight,…}`, primary_muscles ⇄ **Muscle**, secondary_muscles ⇄ Muscle, equipment, instructions, is_custom.
- **Program** → owner — name (e.g. "PPL"), description, is_active.
- **TrainingDay** → Program — name (e.g. "Push"), order.
- **ExerciseSlot** → TrainingDay, → Exercise — order, target_sets, notes, superset_group(nullable).
- **PlannedSet** → ExerciseSlot — order, set_type `{warmup,working,drop,rest_pause,myo_rep,cluster,amrap,backoff,top_set,failure}`, target_reps (range), target_weight / target_pct_1rm, target_rpe / target_rir, tempo, rest_seconds.
- **WorkoutSession** → owner — date, → TrainingDay(nullable for freeform), → Phase(nullable), duration, notes, bodyweight.
- **LoggedExercise** → WorkoutSession, → Exercise — order, superset_group.
- **LoggedSet** → LoggedExercise — order, set_type, reps, weight, rpe/rir, is_completed, is_pr(derived), e1rm(derived).
- **(Mesocycle, optional v1)** → Program — week count, progression_scheme `{linear,double,rir_autoreg,custom}`, deload weeks.
- **Muscle** — reference table (chest, lats, quads, …) for volume analytics.

### Supplements
- **Supplement** → owner — name, brand, form `{capsule,tablet,powder,liquid,…}`, serving_size, target_benefits(tags), notes; **SupplementNutrient** → Supplement, → Nutrient, amount/serving (**feeds nutrition totals**).
- **SupplementSchedule** → Supplement, → owner — dose (servings), timing `{wake,pre_workout,post_workout,with_meal,before_bed,custom}`, cadence `{daily,weekly_n,cyclical}`, days_on/days_off, start/end.
- **SupplementLog** → owner, → Supplement — datetime, dose, status `{taken,skipped}`.

### Medications & Performance Enhancers
- **Compound** → owner(null=global seed) — name, drug_class `{aas,peptide,sarm,ai,serm,ancillary,prescription,hgh,other}`, default_unit `{mg,mcg,iu,ml}`, route `{oral,subq,im,topical,nasal}`, ester(nullable), half_life_hours(nullable), notes.
- **Protocol** → owner — name, kind `{cycle,cruise,trt,blast,ancillary,pct}`, start/end, → Phase(nullable), notes.
- **DoseSchedule** → Protocol, → Compound — dose, unit, cadence `{daily,eod,e3d,2x_week,weekly,custom}`, route, time_of_day, start/end, titration steps (JSON).
- **DoseLog** → owner, → Compound — datetime, dose, unit, route, **injection_site** `{glute_l,glute_r,delt_l,delt_r,vg_l,vg_r,quad_l,quad_r,…}` (rotation tracking), → Protocol(nullable), side_effects, notes.
- **LabPanel** → owner — date, lab_name, notes; **LabResult** → LabPanel — marker (e.g. "Estradiol"), value, unit, ref_low, ref_high.
- **VitalLog** → owner — datetime, type `{blood_pressure_sys,blood_pressure_dia,resting_hr,temp,…}`, value (covers BP for the Telmisartan case).

### Progress Diary
- **PoseType** — reference (front_relaxed, front_double_biceps, side_chest_l/r, back_double_biceps, back_lat_spread, side_triceps_l/r, abs_thighs, most_muscular, custom…).
- **ProgressPhoto** → owner, → PoseType — date, image (private storage key), bodyweight(nullable), → Phase(nullable), notes.
- **CheckInEntry** → owner — date, free_notes, scores (JSON or rows): mood, energy, sleep, hunger, libido, pump, soreness (configurable 1–5/1–10), → Phase(nullable).

### Relationship highlights
- **Phase** is the hub: NutritionTarget, Program/Mesocycle, Protocol, and (by date) every log, photo, lab, and check-in resolve to a phase → enables the dashboard, check-in, and correlations.
- **Nutrient** is shared by Food, Supplement, (and conceptually compounds for completeness) → one daily micro total across food + supplements.
- Template side (Program→Day→Slot→PlannedSet) is separate from the log side (Session→LoggedExercise→LoggedSet) so editing a program never rewrites history.

---

## 7. API Design

- **Base:** `/api/v1/`. Resource-oriented, plural nouns, DRF `ModelViewSet`s + routers.
- **Auth:** `/api/v1/auth/` (login, logout, session, 2FA verify) — session+CSRF (or JWT obtain/refresh).
- **Filtering/paging:** `django-filter` query params; cursor pagination on large logs (sets, doses, diary). Date-range filters everywhere (`?from=&to=`).
- **Examples:**
  - `GET/POST /foods`, `GET /foods/search?q=`, `POST /foods/barcode`
  - `GET/POST /diary-entries?date=2026-05-30`
  - `GET /nutrition/summary?date=` → computed totals (food **+ supplements**) vs target
  - `GET/POST /programs`, `/training-days`, `/exercise-slots`, `/planned-sets`
  - `POST /workout-sessions`, `POST /workout-sessions/{id}/sets`, `GET /exercises/{id}/history`
  - `GET/POST /supplements`, `/supplement-schedules`, `/supplement-logs`
  - `GET/POST /compounds`, `/protocols`, `/dose-schedules`, `/dose-logs`, `/lab-panels`, `/vitals`
  - `GET/POST /progress-photos` (multipart → returns signed GET URL), `/check-ins`
  - `GET /dashboard/today`, `GET /checkin/weekly?week=`
- **Schema/codegen:** `drf-spectacular` serves `/api/schema/`; CI generates the TS client and **fails on drift**.
- **Computed fields** (e1RM, daily totals, active-concentration curve, volume) live in serializers/services, not the client.

---

## 8. Frontend Architecture (SvelteKit / Svelte 5)

- **Routing (route groups):**
  - `(auth)/login`, `(auth)/2fa`
  - `(app)/dashboard`
  - `(app)/nutrition` (diary, foods, recipes, targets)
  - `(app)/training` (programs, day editor, **log session**, history, exercises)
  - `(app)/supplements`
  - `(app)/medications` (compounds, protocols, **log dose**, bloodwork, vitals)
  - `(app)/diary` (photos, compare, check-ins)
  - `(app)/phases`, `(app)/settings`
- **Data loading:** SvelteKit `load` for SSR/initial data; **svelte-query** for client caching, mutations, and optimistic updates (fast logging).
- **State:** prefer server state; small **runes-based** stores (`$state`) for UI/session/active-workout/rest-timer. No heavy global store.
- **Components:** `lib/components/ui` (buttons, inputs, dialogs via Bits UI), `lib/components/charts` (LayerChart wrappers), `lib/components/forms` (superforms + zod). Shared "logger" patterns reused by training/nutrition/dose loggers.
- **Design system:** Tailwind tokens, dark-mode default (gym/low-light), large tap targets, mobile-first; responsive to desktop.
- **PWA/offline:** installable; **offline-first logging** — writes queue to IndexedDB (Dexie) and sync when back online (gym dead zones). Camera for barcode/photos via PWA APIs.
- **Charts:** weight trend (smoothed), per-exercise progression & e1RM, weekly volume by muscle, macro/micro rings, bloodwork trends with reference bands, active-concentration curves, phase-annotated overlays.

---

## 9. Cross-cutting Concerns

- **Units & conversions:** store canonical (kg, cm, g, mg/mcg/IU); convert at the edge per user pref. Centralize conversion utils + tests.
- **Time & timezones:** store UTC; display in profile timezone. "Day" boundaries respect local tz (critical for diary/dose adherence).
- **Reminders/notifications:** Celery beat schedules → **Web Push (VAPID)** for PWA; optional email. Doses, supplements, photos, due bloodwork.
- **Audit/history:** generic `AuditLog` to satisfy "tracking changes" (esp. protocol/dose edits).
- **Validation:** zod on the client, DRF serializers on the server (never trust client).
- **Export/import:** full JSON export + per-module CSV; PDF for check-in/bloodwork (share with doctor/coach). Import custom foods.
- **Accessibility & i18n:** semantic HTML, keyboard support, ARIA via primitives; i18n-ready strings even if English-first.

---

## 10. Security, Privacy & Legal  *(high priority — sensitive data)*

This app stores **special-category health data** and records of **controlled-substance use**.
Treat privacy as a core feature.

- **Hosting:** recommend **self-hosted / single-tenant** (you own the box and the data). If it
  ever becomes multi-user/SaaS, add GDPR/health-data compliance, explicit consent, DPA, etc.
- **Encryption:** TLS in transit (HSTS); encryption at rest for DB volume + media bucket;
  **app-layer field encryption** for the most sensitive tables (medications, dose logs,
  bloodwork) via e.g. Fernet — so a DB dump alone isn't enough.
- **Media:** private bucket, **short-lived signed URLs**, no public objects, no EXIF/GPS leakage
  (strip metadata on upload); optional on-device blur for progress photos.
- **Auth hardening:** 2FA (TOTP), `django-axes` lockout, strong session cookies
  (`HttpOnly`, `Secure`, `SameSite`), CSRF, rate limiting, CSP.
- **Data ownership:** one-click full **export** and **account/data deletion**.
- **No third-party trackers** on health data. If analytics at all, self-hosted (Plausible/Umami),
  excluding any PHI.
- **Medical/legal disclaimer (prominent, in-app):** BBTracker is a **personal tracking and
  journaling tool**, not a medical device and **not medical advice**. It does not recommend,
  prescribe, or endorse any substance, dose, or protocol; the user enters their own data. It
  encourages professional medical supervision and regular bloodwork. (Place at onboarding +
  in the medications module footer.) The medications module is explicitly framed for
  **personal record-keeping and harm reduction** (monitoring bloodwork, BP, side effects,
  injection-site rotation), never as guidance.

---

## 11. Project Structure (monorepo)

```
BBTracker/
├─ backend/
│  ├─ config/                # settings (base/dev/prod), urls, asgi/wsgi, celery
│  ├─ apps/
│  │  ├─ accounts/           # user, profile, 2FA, auth endpoints
│  │  ├─ core/               # phases, tags, attachments, audit, body metrics, dashboard, checkin
│  │  ├─ nutrition/          # nutrients, foods, servings, recipes, diary, targets
│  │  ├─ training/           # muscles, exercises, programs, days, slots, planned/logged sets, sessions
│  │  ├─ supplements/
│  │  ├─ medications/        # compounds, protocols, schedules, dose logs, labs, vitals
│  │  ├─ diary/              # pose types, progress photos, check-ins
│  │  └─ integrations/       # off/usda sync, export/import, pdf reports
│  ├─ manage.py
│  └─ pyproject.toml
├─ frontend/
│  └─ src/
│     ├─ lib/{api,components/{ui,charts,forms},stores,utils}/
│     └─ routes/{(auth),(app)/...}/
├─ infra/                    # Dockerfiles, caddy/nginx, github actions, backup scripts
├─ docs/
├─ docker-compose.yml
├─ README.md
└─ IMPLEMENTATION_PLAN.md    # this file
```

---

## 12. Implementation Roadmap

Phases are ordered by value + independence. Each phase ends with: migrations, API + typed
client, frontend, tests, and a deployable build (DoD = "demoable & tested").
Sizes are relative T-shirt estimates for a solo dev (S/M/L), not calendar promises.

| # | Phase | Scope | Size |
|---|---|---|---|
| **0** | **Foundation** | Repo + docker-compose (Postgres/Redis/MinIO); Django+DRF skeleton; SvelteKit+Tailwind; **accounts + 2FA + session auth**; profile; OpenAPI→TS codegen; CI; deploy pipeline; app shell + nav + dashboard placeholder | **M** |
| **1** | **Training MVP** | Exercise library; Program→Day→Slot→PlannedSet builder; **workout logger** (set types, rest timer, plate calc, repeat-last); history; e1RM + PR; basic charts | **L** |
| **2** | **Nutrition** | Nutrient seed; foods + custom; diary + meals; daily targets & rings; OFF/USDA import + barcode; recipes | **L** |
| **3** | **Supplements + Medications** | Supplement catalog/schedules/logs (+micros into nutrition); compound library; protocols; **dose logger** (+injection-site rotation); **bloodwork & vitals**; active-curve viz | **L** |
| **4** | **Progress Diary** | Pose types; private photo upload (signed URLs, EXIF strip); check-in scores; **compare view** | **M** |
| **5** | **Self-coaching layer** | **Phases timeline** wired across modules; unified **Dashboard "Today"**; **weekly Check-in** + PDF export; correlations/overlays | **M–L** |
| **6** | **Polish** | PWA offline logging queue; web-push reminders; full export/delete; adaptive nutrition targets; volume landmarks; mesocycle progression | **L** |

> Rationale for order: **Training first** — most self-contained and immediately useful
> (replaces Strong day one). Nutrition next (replaces Cronometer). Then the
> supplement/medication monitoring backbone. Diary is light. Phase 5 is where the four
> modules become *one coach*. Phase 6 is the mobile/quality-of-life layer.

---

## 13. Testing Strategy

- **Backend:** `pytest` + `pytest-django` + `factory_boy`; unit tests for computed services
  (e1RM, daily nutrition totals incl. supplements, active-concentration curve, volume,
  unit conversions, day-boundary/timezone logic); DRF `APIClient` for endpoint/permission tests
  (owner isolation is critical — users must never see others' data).
- **Frontend:** Vitest + Testing Library for components (loggers, forms); contract tests
  against the generated client.
- **E2E:** Playwright happy-paths — log a workout, log a day of food, log a dose, upload a photo,
  generate a check-in.
- **CI gates:** lint (ruff/eslint), types (mypy/tsc), tests, **OpenAPI schema-drift check**,
  build. Coverage target ~80% on services/serializers.

---

## 14. DevOps / Deployment

- **Local:** `docker-compose up` → Postgres + Redis + MinIO + backend + frontend; seed scripts
  (nutrients, muscles, common exercises, pose types, a starter compound library).
- **CI/CD:** GitHub Actions (test/build → image push → deploy).
- **Prod (recommended self-host):** single VPS, Docker Compose, **Caddy** (auto-HTTPS),
  Postgres with encrypted volume, MinIO or R2 for media.
  *Managed alternative:* Fly.io / Railway / Render (mind data-residency for health data).
- **Backups:** nightly `pg_dump` + object-store versioning, off-box, **test restores**.
- **Secrets:** env via `django-environ`; never commit; rotate.
- **Observability:** structured logs; optional self-hosted Sentry for errors (scrub PHI).

---

## 15. Risks & Open Decisions

| Decision | Options | Recommendation |
|---|---|---|
| Auth | Session+CSRF+2FA · JWT (SimpleJWT) | **Session+2FA** for privacy-first single/few-user; revisit if native clients added |
| Hosting | Self-host · Managed PaaS | **Self-host** for data ownership of sensitive data |
| Food data | OFF · USDA · MFP-style crowd | **OFF + USDA** (open/licensed); never scrape proprietary DBs (e.g. Cronometer's NCCDB) |
| Background jobs | Celery+Redis · Huey/django-q2 | Celery if doing push/reports early; otherwise start with Huey, migrate later |
| Charts | LayerChart · Chart.js · ECharts · uPlot | LayerChart default; uPlot for dense time-series |
| Offline scope | Full offline · Logging-only · Online-only | **Logging-only offline** (gym) in Phase 6 |
| **Apple Health** | Direct (impossible on web) · Manual import · Capacitor wrapper | **PWA-first**; web cannot read HealthKit — defer native bridge (Capacitor) to post-v1 if wanted |
| Native mobile | PWA · Capacitor wrap · React/Native rewrite | **PWA**; optionally wrap with **Capacitor** later for HealthKit + push + camera |

**Known constraints to flag early**
- **HealthKit/Apple Health is not accessible from a browser.** The "Apple Health–like"
  experience here is delivered by our own medications/supplements modules; true HealthKit
  sync requires a native companion (Capacitor) and is out of scope for v1.
- Proprietary food databases can't be legally redistributed; expect to build food data from
  OFF/USDA + the user's custom foods over time.

---

## 16. Immediate Next Steps (Phase 0)

> **Local toolchain note:** this machine has **Python 3.9.6** and **Node 18.17.0**. Django 5.x
> requires **Python 3.10+** (target 3.12), and Node 20+ is recommended for current SvelteKit.
> Easiest fix: develop **inside Docker** (Docker 28 is already installed) so the host versions
> don't matter; or install pyenv (Python 3.12) + nvm (Node 20+) locally.

1. Initialize monorepo + `git init`; add `docker-compose.yml` (Postgres, Redis, MinIO).
2. Scaffold Django project (`config/` + `accounts`, `core` apps), DRF, drf-spectacular, CORS.
3. Implement **accounts**: register/login/logout, session auth, **TOTP 2FA**, Profile.
4. Scaffold SvelteKit + Tailwind + Bits UI; auth flow; app shell + nav; dashboard placeholder.
5. Wire **OpenAPI → TS client** codegen and the CI pipeline (lint/type/test/schema-drift).
6. Seed reference data (nutrients, muscles, pose types, starter exercises/compounds).
7. Land a thin vertical slice (login → dashboard) deployed to the target host.

Then proceed to **Phase 1 (Training MVP)**.
