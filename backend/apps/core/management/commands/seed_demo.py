"""Build a comprehensive demo dataset for client showcases.

Creates a single demo athlete's journey across two phases:

* **20-week off-season bulk** (2025-09-08 → 2026-01-25): 73 kg → 97 kg, with
  weekly progress photos (loaded from disk), an Upper/Lower program with
  progressive overload, a high-surplus nutrition history that ramps with
  bodyweight, an off-season "blast" protocol (Test/Deca/EQ + ancillaries) with
  rotated injection sites, body measurements and two bloodwork panels.
* **12-week maintenance** (2026-01-26 → 2026-04-19): bodyweight held, calories
  pulled back to maintenance, a cruise protocol — check-in notes but no photos.

Realistic gaps are baked in (a September holiday, the December holidays, a
mid-January cold) and explained in the daily check-in notes.

Everything is owner-scoped to a dedicated demo account; global/seeded reference
data (foods, exercises, compounds, poses, markers, injection sites) is reused.
The command is idempotent and reproducible (fixed RNG seed) so it can be re-run
locally or on the self-hosted instance:

    python manage.py seed_demo --photos-dir /photos

NOT medical advice — this is fabricated demonstration data.
"""
from __future__ import annotations

import random
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

# Timeline (see module docstring). Bulk first photo (Sep 10) sits in week 1, which
# with exact 20 + 12 weeks lands the maintenance end on Sun 2026-04-19.
MAINT_END = date.today()
MAINT_START = MAINT_END - timedelta(weeks=12)
BULK_END = MAINT_START - timedelta(days=1)
BULK_START = BULK_END - timedelta(weeks=20)

# Pose-file prefix → seeded Pose slug (the user shoots the four relaxed poses).
POSE_FILES = {
    "front": "front-relaxed",
    "back": "back-relaxed",
    "side_l": "side-relaxed-left",
    "side_r": "side-relaxed-right",
}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".jp2", ".webp", ".heic"}

# Off-season holiday / illness windows → explained in check-in notes, and photos
# / training / doses are skipped across them.
GAP_WINDOWS = [
    (date(2025, 9, 13), date(2025, 9, 27),
     "On holiday (Italy) — eating out, light hotel-gym sessions, no photos this week."),
    (date(2025, 12, 18), date(2025, 12, 29),
     "Holiday season — family time, kept training loose, skipped the weekly shoot."),
    (date(2026, 1, 7), date(2026, 1, 16),
     "Caught a cold — pulled training back for a few days to recover."),
]


def in_gap(d: date):
    for start, end, note in GAP_WINDOWS:
        if start <= d <= end:
            return note
    return None


class Command(BaseCommand):
    help = "Wipe and build a two-phase demo dataset (off-season bulk + maintenance)."

    def add_arguments(self, parser):
        parser.add_argument("--photos-dir", default="/photos",
                            help="Directory of YYYY-MM-DD subfolders with pose photos.")
        parser.add_argument("--email", default="demo@tmlittau.com")
        parser.add_argument("--coach-email", default="coaching@tmlittau.com",
                            help="A coach account, linked to the demo as an active client.")
        parser.add_argument("--password", default="DemoPass2026!")
        parser.add_argument("--keep-users", nargs="*", default=["info@tmlittau.com"],
                            help="Emails (besides the demo account) to NOT delete.")
        parser.add_argument("--no-wipe", action="store_true",
                            help="Skip all clearing; just build (additive — may duplicate).")
        parser.add_argument("--demo-only", action="store_true",
                            help="Reset ONLY the demo account's data, leaving every other "
                                 "user untouched. Safe + idempotent — use this on prod.")

    def handle(self, *args, **opts):
        random.seed(42)
        self.opts = opts
        self.email = opts["email"]
        self.coach_email = opts["coach_email"]
        self.photos_dir = Path(opts["photos_dir"])
        demo_only = opts["demo_only"]
        full_wipe = not opts["no_wipe"] and not demo_only

        user = self._ensure_user()
        # Photo blobs live in object storage (non-transactional); clear the demo
        # account's blobs up front so a re-run never orphans them.
        if full_wipe or demo_only:
            self._wipe_demo_photos(user)

        with transaction.atomic():
            if full_wipe:
                self._wipe(keep={self.email, self.coach_email, *opts["keep_users"]})
            elif demo_only:
                self._wipe_demo(user)
            refs = self._load_refs()
            self._ensure_extra_compounds(user, refs)
            supplements = self._build_supplements(user, refs)
            targets = self._build_nutrition_targets(user)
            program = self._build_program(user, refs)
            protocols = self._build_protocols(user, refs, supplements)
            self._build_phases(user, targets, program, protocols)
            self._build_checkins(user)
            self._build_workouts(user, program, refs)
            self._build_nutrition_log(user, refs, targets)
            self._build_doses(user, protocols, refs)
            self._build_measurements(user)
            self._build_bloodwork(user)
            self._ensure_coach(user)

        n_photos = self._build_photos(user)

        mode = "full wipe" if full_wipe else ("demo-only reset" if demo_only else "additive")
        self.stdout.write(self.style.SUCCESS(
            f"Demo ready for {self.email} (password: {opts['password']}) [{mode}]. "
            f"Bulk {BULK_START}→{BULK_END}, Maintenance {MAINT_START}→{MAINT_END}, "
            f"{n_photos} progress photos."
        ))

    # ---- helpers -----------------------------------------------------------
    def _dt(self, d: date, h=9, m=0):
        return timezone.make_aware(datetime.combine(d, time(h, m)))

    def _daterange(self, start: date, end: date):
        d = start
        while d <= end:
            yield d
            d += timedelta(days=1)

    # ---- wipe --------------------------------------------------------------
    def _wipe(self, keep):
        from apps.analysis.models import BodyMeasurement
        from apps.core.models import Phase
        from apps.diary.models import CheckIn, ProgressPhoto
        from apps.nutrition.models import DiaryEntry, Food, Meal, NutritionTarget, Recipe
        from apps.protocols.models import (
            BloodPressureLog,
            BloodResult,
            Compound,
            DoseLog,
            Protocol,
            Supplement,
        )
        from apps.training.models import Exercise, Program, WorkoutSession

        User = get_user_model()

        # 1) Transactional rows first — they PROTECT-reference the custom reference
        #    rows (Food/Compound/Supplement/Exercise), so they must go before both
        #    those rows and the users that own everything.
        DoseLog.objects.all().delete()
        Protocol.objects.all().delete()  # cascades ProtocolItem
        WorkoutSession.objects.all().delete()  # cascades LoggedExercise/Set
        Program.objects.all().delete()  # cascades days/slots/planned sets
        DiaryEntry.objects.all().delete()
        Recipe.objects.all().delete()  # cascades RecipeItem (also PROTECTs Food)
        Meal.objects.all().delete()
        NutritionTarget.objects.all().delete()
        BodyMeasurement.objects.all().delete()
        BloodResult.objects.all().delete()
        BloodPressureLog.objects.all().delete()
        CheckIn.objects.all().delete()
        ProgressPhoto.objects.all().delete()
        Phase.objects.all().delete()

        # 2) Custom reference rows are now unreferenced — keep only the global
        #    (owner=None) seeded library.
        Food.objects.filter(owner__isnull=False).delete()
        Exercise.objects.filter(owner__isnull=False).delete()
        Compound.objects.filter(owner__isnull=False).delete()
        Supplement.objects.filter(owner__isnull=False).delete()

        # 3) Drop the leftover test/e2e accounts (clean cascade now).
        dropped, _ = User.objects.exclude(email__in=keep).delete()
        self.stdout.write(
            f"Wiped all transactional data + dropped non-kept users "
            f"({dropped} rows). Global library kept."
        )

    def _wipe_demo_photos(self, user):
        from apps.diary.models import ProgressPhoto
        from apps.diary.storage import get_storage
        storage = get_storage()
        for p in ProgressPhoto.objects.filter(owner=user):
            for key in (p.object_key, p.thumb_key):
                if key:
                    try:
                        storage.delete(key)
                    except Exception:
                        pass
        ProgressPhoto.objects.filter(owner=user).delete()

    def _wipe_demo(self, user):
        """Delete only the demo account's data — every other user is untouched.

        Safe to run on prod alongside real accounts, and idempotent (re-running
        rebuilds the demo cleanly). Deletion order respects PROTECT FKs.
        """
        from apps.analysis.models import BodyMeasurement
        from apps.core.models import Phase
        from apps.diary.models import CheckIn, ProgressPhoto
        from apps.nutrition.models import DiaryEntry, Food, Meal, NutritionTarget, Recipe
        from apps.protocols.models import (
            BloodPressureLog,
            BloodResult,
            Compound,
            DoseLog,
            Protocol,
            Supplement,
        )
        from apps.training.models import Exercise, Program, WorkoutSession

        DoseLog.objects.filter(owner=user).delete()
        Protocol.objects.filter(owner=user).delete()  # cascades ProtocolItem
        WorkoutSession.objects.filter(owner=user).delete()
        Program.objects.filter(owner=user).delete()
        DiaryEntry.objects.filter(owner=user).delete()
        Recipe.objects.filter(owner=user).delete()
        Meal.objects.filter(owner=user).delete()
        NutritionTarget.objects.filter(owner=user).delete()
        BodyMeasurement.objects.filter(owner=user).delete()
        BloodResult.objects.filter(owner=user).delete()
        BloodPressureLog.objects.filter(owner=user).delete()
        CheckIn.objects.filter(owner=user).delete()
        ProgressPhoto.objects.filter(owner=user).delete()
        Phase.objects.filter(owner=user).delete()
        # The demo account's own custom reference rows (globals are owner=None).
        Food.objects.filter(owner=user).delete()
        Exercise.objects.filter(owner=user).delete()
        Compound.objects.filter(owner=user).delete()
        Supplement.objects.filter(owner=user).delete()
        self.stdout.write(f"Reset demo account {user.email} (other users untouched).")

    # ---- user --------------------------------------------------------------
    def _ensure_user(self):
        from apps.accounts.models import Profile
        User = get_user_model()
        user, _ = User.objects.get_or_create(
            email=self.email, defaults={"is_active": True}
        )
        user.is_active = True
        user.set_password(self.opts["password"])
        user.save()
        # Verified, primary email so headless login works without a verification step.
        try:
            from allauth.account.models import EmailAddress
            EmailAddress.objects.update_or_create(
                user=user, email=self.email,
                defaults={"verified": True, "primary": True},
            )
        except Exception:
            pass
        Profile.objects.update_or_create(
            user=user,
            defaults={
                "sex": "male",
                "date_of_birth": date(1994, 4, 18),
                "height_cm": Decimal("181.0"),
                "unit_system": "metric",
                "timezone": "Europe/Amsterdam",
            },
        )
        self.stdout.write(f"Demo user ready: {self.email}")
        return user

    def _ensure_coach(self, client):
        """A coach account with an active link to the demo client, so the coaching
        interface is demoable: log in as the coach to view the demo's data."""
        from apps.coaching.models import CoachClientLink, LinkStatus
        User = get_user_model()
        coach, _ = User.objects.get_or_create(
            email=self.coach_email, defaults={"is_active": True}
        )
        coach.is_active = True
        coach.is_coach = True
        coach.first_name = "Coach"
        coach.set_password(self.opts["password"])
        coach.save()
        try:
            from allauth.account.models import EmailAddress
            EmailAddress.objects.update_or_create(
                user=coach, email=self.coach_email,
                defaults={"verified": True, "primary": True},
            )
        except Exception:
            pass
        CoachClientLink.objects.update_or_create(
            coach=coach, client=client,
            defaults={
                "status": LinkStatus.ACTIVE,
                "responded_at": timezone.now(),
                "can_edit_prescriptions": True,
            },
        )
        self.stdout.write(f"Coach ready: {self.coach_email} → coaches {client.email}")

    def _load_refs(self):
        from apps.diary.models import Pose
        from apps.nutrition.models import Food, Nutrient
        from apps.protocols.models import Compound, InjectionSite
        from apps.training.models import Exercise
        return {
            "poses": {p.slug: p for p in Pose.objects.all()},
            "foods": {f.name: f for f in Food.objects.filter(owner__isnull=True)},
            "energy": Nutrient.objects.get(slug="energy"),
            "exercises": {e.name: e for e in Exercise.objects.filter(owner__isnull=True)},
            "compounds": {c.name: c for c in Compound.objects.filter(owner__isnull=True)},
            "im_sites": list(InjectionSite.objects.filter(
                region__in=["ventroglute", "glute", "quad", "delt", "pec"]).order_by("id")),
            "subq_sites": list(InjectionSite.objects.filter(region="abdomen").order_by("id")),
        }

    # ---- extra compounds (not in the global seed library) ------------------
    def _ensure_extra_compounds(self, user, refs):
        """Create demo-owned compounds missing from the global library; merge into refs."""
        from apps.protocols.enums import CompoundClass, DoseUnit, Route
        from apps.protocols.models import Compound
        # name, class, unit, route, half-life (h), notes
        extra = [
            ("Cardarine (GW-501516)", CompoundClass.OTHER, DoseUnit.MG, Route.ORAL, 24,
             "PPARδ agonist — endurance + fat-oxidation / lipid support."),
            ("MK-677 (Ibutamoren)", CompoundClass.OTHER, DoseUnit.MG, Route.ORAL, 24,
             "Oral GH secretagogue — appetite, sleep, recovery."),
            ("Proviron (Mesterolone)", CompoundClass.ANABOLIC, DoseUnit.MG, Route.ORAL, 12,
             "Lowers SHBG, raises free testosterone, libido."),
            ("GHK-Cu", CompoundClass.PEPTIDE, DoseUnit.MCG, Route.SUBQ, 1,
             "Copper peptide — skin, collagen, wound healing."),
            ("KPV", CompoundClass.PEPTIDE, DoseUnit.MCG, Route.SUBQ, 2,
             "Anti-inflammatory tripeptide — gut + systemic recovery."),
            ("TB-500 (Thymosin β4)", CompoundClass.PEPTIDE, DoseUnit.MG, Route.SUBQ, 60,
             "Recovery peptide — commonly paired with BPC-157."),
        ]
        for name, cls, unit, route, hl, notes in extra:
            if name in refs["compounds"]:
                continue
            refs["compounds"][name] = Compound.objects.create(
                owner=user, name=name, compound_class=cls, default_unit=unit,
                default_route=route, half_life_hours=Decimal(str(hl)), notes=notes,
            )

    # ---- supplements -------------------------------------------------------
    def _build_supplements(self, user, refs):
        """Create the demo athlete's supplement stack (with micronutrient content)."""
        from apps.nutrition.models import Nutrient
        from apps.protocols.models import Supplement, SupplementNutrient
        nut = {n.slug: n for n in Nutrient.objects.all()}
        # name, serving_label, benefit, {nutrient_slug: amount_per_serving}
        specs = [
            ("Vitamin D3 + K2", "1 softgel", "Bone / immune / hormonal",
             {"vitamin_d": 125, "vitamin_k": 100}),
            ("Omega-3 fish oil", "2 softgels", "Heart, joints, lipid profile", {}),
            ("Magnesium glycinate", "2 capsules", "Sleep, cramps, blood pressure",
             {"magnesium": 400}),
            ("Zinc picolinate", "1 capsule", "Immune + testosterone support", {"zinc": 25}),
            ("Vitamin C", "1 tablet", "Antioxidant", {"vitamin_c": 1000}),
            ("Creatine monohydrate", "1 scoop (5 g)", "Strength + cell volume", {}),
            ("NAC", "1 capsule", "Liver + glutathione antioxidant", {}),
            ("CoQ10", "1 softgel", "Heart / blood-pressure support", {}),
            ("Berberine", "1 capsule", "Glucose + lipid management", {}),
            ("Citrus bergamot", "1 capsule", "Cholesterol support on-cycle", {}),
            ("Psyllium husk fiber", "1 scoop", "Digestion, cholesterol, satiety", {"fiber": 5}),
            ("Ashwagandha (KSM-66)", "1 capsule", "Stress / cortisol", {}),
            ("Taurine", "1 scoop", "Cramps, pumps, blood pressure", {}),
            ("Multivitamin", "1 serving", "Daily micronutrient base",
             {"vitamin_c": 300, "zinc": 15, "magnesium": 100, "vitamin_b12": 50, "vitamin_d": 25}),
            ("L-Citrulline", "1 scoop", "Pumps / blood flow", {}),
        ]
        out = {}
        for name, serving, benefit, micros in specs:
            s = Supplement.objects.create(
                owner=user, name=name, serving_label=serving, target_benefit=benefit,
            )
            for slug, amt in micros.items():
                if slug in nut:
                    SupplementNutrient.objects.create(
                        supplement=s, nutrient=nut[slug], amount_per_serving=Decimal(str(amt)),
                    )
            out[name] = s
        return out

    # ---- nutrition targets -------------------------------------------------
    def _build_nutrition_targets(self, user):
        from apps.nutrition.models import NutritionTarget
        specs = [
            ("Off-season surplus · phase 1", 3600, 200, 430, 110, 40, False),
            ("Off-season surplus · phase 2", 3950, 210, 480, 120, 42, False),
            ("Off-season surplus · phase 3", 4250, 220, 530, 125, 45, False),
            ("Maintenance", 3150, 195, 330, 95, 40, True),
        ]
        out = {}
        for name, kcal, p, c, f, fib, active in specs:
            out[name] = NutritionTarget.objects.create(
                owner=user, name=name, is_active=active, day_type="any",
                calories=Decimal(kcal), protein_g=Decimal(p), carb_g=Decimal(c),
                fat_g=Decimal(f), fiber_g=Decimal(fib),
            )
        return out

    # ---- training program --------------------------------------------------
    def _build_program(self, user, refs):
        from apps.training.enums import SetType
        from apps.training.models import (
            ExerciseSlot,
            PlannedSet,
            Program,
            TrainingDay,
        )
        program = Program.objects.create(
            owner=user, name="Upper / Lower · 4-day", is_active=True,
            description="Four-day upper/lower split run through the off-season and maintenance.",
        )
        days = {
            "Upper A": ["Barbell Bench Press", "Barbell Row", "Overhead Press",
                        "Lat Pulldown", "Triceps Pushdown", "Barbell Curl"],
            "Lower A": ["Barbell Back Squat", "Romanian Deadlift", "Leg Press",
                        "Leg Curl", "Standing Calf Raise"],
            "Upper B": ["Incline Barbell Bench Press", "Pull-up", "Dumbbell Shoulder Press",
                        "Seated Cable Row", "Lateral Raise", "Dumbbell Curl"],
            "Lower B": ["Conventional Deadlift", "Front Squat", "Leg Extension",
                        "Leg Curl", "Standing Calf Raise"],
        }
        for order, (dname, exs) in enumerate(days.items()):
            day = TrainingDay.objects.create(program=program, name=dname, order=order)
            for so, ename in enumerate(exs):
                ex = refs["exercises"].get(ename)
                if not ex:
                    continue
                slot = ExerciseSlot.objects.create(day=day, exercise=ex, order=so)
                for ps in range(3):
                    PlannedSet.objects.create(
                        slot=slot, order=ps, set_type=SetType.WORKING,
                        target_reps_low=6, target_reps_high=10,
                    )
        return program

    # ---- protocols ---------------------------------------------------------
    def _build_protocols(self, user, refs, supplements):
        from apps.protocols.enums import DoseUnit, Frequency, Route, TimeOfDay
        from apps.protocols.models import Protocol, ProtocolItem
        C = refs["compounds"]

        def item(proto, cname, dose, unit, route, freq, days=None, times=None, order=0, benefit=""):
            comp = C.get(cname)
            if not comp:
                return
            ProtocolItem.objects.create(
                protocol=proto, compound=comp, dose_amount=Decimal(str(dose)), dose_unit=unit,
                route=route, frequency=freq, days_of_week=days or [], times_of_day=times or [],
                target_benefit=benefit, order=order,
            )

        def supp_item(proto, sname, dose, unit, freq, times=None, order=0):
            s = supplements.get(sname)
            if not s:
                return
            ProtocolItem.objects.create(
                protocol=proto, supplement=s, dose_amount=Decimal(str(dose)), dose_unit=unit,
                route="", frequency=freq, times_of_day=times or [],
                target_benefit=s.target_benefit, order=order,
            )

        # Year-round supplement stack (same in both blocks).
        supp_stack = [
            ("Vitamin D3 + K2", 1, DoseUnit.CAPSULE, [TimeOfDay.AM]),
            ("Omega-3 fish oil", 2, DoseUnit.CAPSULE, [TimeOfDay.AM]),
            ("Magnesium glycinate", 2, DoseUnit.CAPSULE, [TimeOfDay.NIGHT]),
            ("Zinc picolinate", 1, DoseUnit.CAPSULE, [TimeOfDay.NIGHT]),
            ("Vitamin C", 1, DoseUnit.TABLET, [TimeOfDay.AM]),
            ("Creatine monohydrate", 1, DoseUnit.SERVING, [TimeOfDay.AM]),
            ("NAC", 1, DoseUnit.CAPSULE, [TimeOfDay.AM]),
            ("CoQ10", 1, DoseUnit.CAPSULE, [TimeOfDay.AM]),
            ("Berberine", 1, DoseUnit.CAPSULE, [TimeOfDay.NOON]),
            ("Citrus bergamot", 1, DoseUnit.CAPSULE, [TimeOfDay.AM]),
            ("Psyllium husk fiber", 1, DoseUnit.SERVING, [TimeOfDay.NIGHT]),
            ("Ashwagandha (KSM-66)", 1, DoseUnit.CAPSULE, [TimeOfDay.NIGHT]),
            ("Taurine", 1, DoseUnit.SERVING, [TimeOfDay.AM]),
            ("Multivitamin", 1, DoseUnit.SERVING, [TimeOfDay.AM]),
            ("L-Citrulline", 1, DoseUnit.SERVING, [TimeOfDay.AM]),
        ]

        def add_supps(proto):
            for i, (sname, dose, unit, times) in enumerate(supp_stack):
                supp_item(proto, sname, dose, unit, Frequency.DAILY, times=times, order=30 + i)

        blast = Protocol.objects.create(
            owner=user, name="Off-season blast", is_active=False,
            started_on=BULK_START, ended_on=BULK_END,
            notes="Off-season mass protocol. Bloodwork mid-cycle; AI titrated to E2.",
        )
        # Injectables Mon(0)/Thu(3); hCG Tue(1)/Fri(4); orals daily/EOD.
        item(blast, "Testosterone Enanthate", 250, DoseUnit.MG, Route.IM, Frequency.SPECIFIC_DAYS,
             days=[0, 3], times=[TimeOfDay.AM], order=0, benefit="Primary anabolic")
        item(blast, "Nandrolone Decanoate", 150, DoseUnit.MG, Route.IM, Frequency.SPECIFIC_DAYS,
             days=[0, 3], times=[TimeOfDay.AM], order=1, benefit="Mass + joint comfort")
        item(blast, "Boldenone Undecylenate", 200, DoseUnit.MG, Route.IM, Frequency.SPECIFIC_DAYS,
             days=[0, 3], times=[TimeOfDay.AM], order=2, benefit="Appetite + endurance")
        item(blast, "hCG", 500, DoseUnit.IU, Route.SUBQ, Frequency.SPECIFIC_DAYS,
             days=[1, 4], times=[TimeOfDay.PM], order=3, benefit="Testicular function")
        item(blast, "Anastrozole", 0.5, DoseUnit.MG, Route.ORAL, Frequency.EOD,
             times=[TimeOfDay.AM], order=4, benefit="Estrogen control")
        item(blast, "Cialis (Tadalafil)", 5, DoseUnit.MG, Route.ORAL, Frequency.DAILY,
             times=[TimeOfDay.PM], order=5, benefit="Blood pressure / pumps")
        item(blast, "BPC-157", 250, DoseUnit.MCG, Route.SUBQ, Frequency.DAILY,
             times=[TimeOfDay.AM], order=6, benefit="Joint / tendon recovery")
        item(blast, "Proviron (Mesterolone)", 50, DoseUnit.MG, Route.ORAL, Frequency.DAILY,
             times=[TimeOfDay.AM], order=7, benefit="Free-test / libido")
        item(blast, "MK-677 (Ibutamoren)", 25, DoseUnit.MG, Route.ORAL, Frequency.DAILY,
             times=[TimeOfDay.NIGHT], order=8, benefit="GH / appetite / sleep")
        item(blast, "Cardarine (GW-501516)", 20, DoseUnit.MG, Route.ORAL, Frequency.DAILY,
             times=[TimeOfDay.AM], order=9, benefit="Endurance / lipids")
        item(blast, "CJC-1295 (no DAC)", 100, DoseUnit.MCG, Route.SUBQ, Frequency.DAILY,
             times=[TimeOfDay.NIGHT], order=10, benefit="GH pulse")
        item(blast, "Ipamorelin", 200, DoseUnit.MCG, Route.SUBQ, Frequency.DAILY,
             times=[TimeOfDay.NIGHT], order=11, benefit="GH pulse")
        item(blast, "GHK-Cu", 2000, DoseUnit.MCG, Route.SUBQ, Frequency.EOD,
             times=[TimeOfDay.PM], order=12, benefit="Skin / collagen")
        item(blast, "TB-500 (Thymosin β4)", 2.5, DoseUnit.MG, Route.SUBQ, Frequency.WEEKLY,
             times=[TimeOfDay.AM], order=13, benefit="Recovery")
        item(blast, "Telmisartan", 40, DoseUnit.MG, Route.ORAL, Frequency.DAILY,
             times=[TimeOfDay.AM], order=14, benefit="Blood pressure")

        cruise = Protocol.objects.create(
            owner=user, name="Maintenance cruise", is_active=True,
            started_on=MAINT_START, ended_on=MAINT_END,
            notes="Cruise dose between blocks. Keep estrogen in range, support natural function.",
        )
        item(cruise, "Testosterone Enanthate", 75, DoseUnit.MG, Route.IM, Frequency.SPECIFIC_DAYS,
             days=[0, 3], times=[TimeOfDay.AM], order=0, benefit="Cruise base")
        item(cruise, "hCG", 500, DoseUnit.IU, Route.SUBQ, Frequency.SPECIFIC_DAYS,
             days=[1, 4], times=[TimeOfDay.PM], order=1, benefit="Testicular function")
        item(cruise, "Anastrozole", 0.25, DoseUnit.MG, Route.ORAL, Frequency.EVERY_3_DAYS,
             times=[TimeOfDay.AM], order=2, benefit="Estrogen control")
        item(cruise, "Cialis (Tadalafil)", 5, DoseUnit.MG, Route.ORAL, Frequency.DAILY,
             times=[TimeOfDay.PM], order=3, benefit="Blood pressure")
        item(cruise, "BPC-157", 250, DoseUnit.MCG, Route.SUBQ, Frequency.DAILY,
             times=[TimeOfDay.AM], order=4, benefit="Healing")
        item(cruise, "TB-500 (Thymosin β4)", 2.5, DoseUnit.MG, Route.SUBQ, Frequency.WEEKLY,
             times=[TimeOfDay.AM], order=5, benefit="Recovery")
        item(cruise, "KPV", 500, DoseUnit.MCG, Route.SUBQ, Frequency.DAILY,
             times=[TimeOfDay.AM], order=6, benefit="Gut / anti-inflammatory")
        item(cruise, "GHK-Cu", 2000, DoseUnit.MCG, Route.SUBQ, Frequency.EOD,
             times=[TimeOfDay.PM], order=7, benefit="Skin / collagen")
        item(cruise, "Cardarine (GW-501516)", 10, DoseUnit.MG, Route.ORAL, Frequency.DAILY,
             times=[TimeOfDay.AM], order=8, benefit="Lipid support")

        add_supps(blast)
        add_supps(cruise)
        return {"blast": blast, "cruise": cruise}

    # ---- phases ------------------------------------------------------------
    def _build_phases(self, user, targets, program, protocols):
        from apps.core.enums import PhaseType
        from apps.core.models import Phase, PhaseAdjustment

        bulk = Phase.objects.create(
            owner=user, name="Off-season bulk", phase_type=PhaseType.BULK,
            start_date=BULK_START, end_date=BULK_END,
            notes=("20-week off-season. Goal 73 → 97 kg — build mass while keeping "
                   "conditioning reasonable."),
        )
        # Calorie ramp as the scale climbs — the coaching story behind the surplus.
        PhaseAdjustment.objects.create(
            phase=bulk, effective_date=BULK_START, reason="Start surplus",
            nutrition_target=targets["Off-season surplus · phase 1"], program=program,
            protocol=protocols["blast"],
        )
        PhaseAdjustment.objects.create(
            phase=bulk, effective_date=BULK_START + timedelta(weeks=7),
            reason="Weight climbing — add calories",
            nutrition_target=targets["Off-season surplus · phase 2"], program=program,
            protocol=protocols["blast"],
        )
        PhaseAdjustment.objects.create(
            phase=bulk, effective_date=BULK_START + timedelta(weeks=14),
            reason="Push the final stretch",
            nutrition_target=targets["Off-season surplus · phase 3"], program=program,
            protocol=protocols["blast"],
        )
        maint = Phase.objects.create(
            owner=user, name="Maintenance", phase_type=PhaseType.MAINTAIN,
            start_date=MAINT_START, end_date=MAINT_END,
            notes=("12-week maintenance to settle in at the new bodyweight and recover "
                   "markers before the next block."),
        )
        PhaseAdjustment.objects.create(
            phase=maint, effective_date=MAINT_START, reason="Pull back to maintenance + cruise",
            nutrition_target=targets["Maintenance"], program=program,
            protocol=protocols["cruise"],
        )

    # ---- daily check-ins ---------------------------------------------------
    def _bodyweight(self, d: date) -> Decimal:
        if d <= BULK_END:
            frac = (d - BULK_START).days / (BULK_END - BULK_START).days
            base = 73.0 + 24.0 * frac
        else:
            frac = (d - MAINT_START).days / (MAINT_END - MAINT_START).days
            base = 96.8 - 1.2 * frac  # settle slightly off the bulk peak
        # weekly water wobble + daily noise
        wobble = 0.5 * random.uniform(-1, 1) + 0.35 * ((d.toordinal() % 7) - 3) / 3
        return Decimal(f"{base + wobble + random.gauss(0, 0.25):.1f}")

    def _build_checkins(self, user):
        from apps.diary.models import CheckIn
        rows = []
        photo_days = self._photo_dates()
        for d in self._daterange(BULK_START, MAINT_END):
            gap = in_gap(d)
            sick = gap and "cold" in gap
            note = ""
            if gap:
                note = gap
            elif d in photo_days:
                note = random.choice([
                    "Weekly check-in + photos. Strength up, conditioning holding.",
                    "Photo day. Scale moving as planned, sleep solid.",
                    "Check-in shots done — feeling fuller, waist creeping up a touch.",
                ])
            elif d == MAINT_START:
                note = "Switching to maintenance. Calories down, training intensity stays."
            elif random.random() < 0.12:
                note = random.choice([
                    "Good energy in the gym today.", "Appetite high, hitting all meals.",
                    "Bit of fatigue, deload coming.", "Steps in, cardio done.",
                    "Joints feeling good.", "Stress at work, sleep a little short.",
                ])
            energy = 2 if sick else random.randint(3, 5)
            mood = 2 if sick else random.randint(3, 5)
            rows.append(CheckIn(
                owner=user, date=d, bodyweight=self._bodyweight(d),
                systolic=random.randint(122, 138) if d <= BULK_END else random.randint(116, 128),
                diastolic=random.randint(74, 86) if d <= BULK_END else random.randint(70, 80),
                pulse=random.randint(58, 72),
                energy=energy, sleep=random.randint(3, 5), mood=mood,
                motivation=2 if sick else random.randint(3, 5),
                soreness=random.randint(2, 4), notes=note,
            ))
        CheckIn.objects.bulk_create(rows, batch_size=500)
        self.stdout.write(f"Check-ins: {len(rows)}")

    # ---- workouts ----------------------------------------------------------
    # base working weight (kg) + per-week increment; maintenance grows slower.
    LIFTS = {
        "Barbell Bench Press": (80, 1.0), "Barbell Row": (75, 0.9),
        "Overhead Press": (50, 0.6), "Lat Pulldown": (65, 0.8),
        "Triceps Pushdown": (45, 0.5), "Barbell Curl": (32, 0.4),
        "Barbell Back Squat": (100, 1.5), "Romanian Deadlift": (90, 1.2),
        "Leg Press": (180, 4.0), "Leg Curl": (50, 0.7), "Standing Calf Raise": (90, 1.5),
        "Incline Barbell Bench Press": (65, 0.8), "Pull-up": (5, 0.5),
        "Dumbbell Shoulder Press": (26, 0.4), "Seated Cable Row": (65, 0.8),
        "Lateral Raise": (12, 0.25), "Dumbbell Curl": (16, 0.3),
        "Conventional Deadlift": (120, 1.75), "Front Squat": (70, 1.0),
        "Leg Extension": (60, 1.0),
    }

    def _build_workouts(self, user, program, refs):
        from apps.training.enums import SetType
        from apps.training.models import (
            LoggedExercise,
            LoggedSet,
            WorkoutSession,
        )
        days = list(program.days.all().order_by("order"))
        # Mon/Tue/Thu/Fri = the four template days.
        weekday_to_day = {0: days[0], 1: days[1], 3: days[2], 4: days[3]}

        sessions, plan = [], []
        for d in self._daterange(BULK_START, MAINT_END):
            day = weekday_to_day.get(d.weekday())
            if not day:
                continue
            gap = in_gap(d)
            if gap and ("cold" in gap or "Italy" in gap) and random.random() < 0.7:
                continue  # missed during illness / travel
            week = (d - BULK_START).days // 7
            start = self._dt(d, random.randint(7, 18), random.choice([0, 15, 30]))
            s = WorkoutSession(
                owner=user, day=day, name=day.name, started_at=start,
                ended_at=start + timedelta(minutes=random.randint(62, 85)),
                bodyweight=self._bodyweight(d),
            )
            sessions.append(s)
            plan.append((day, week))
        WorkoutSession.objects.bulk_create(sessions)

        # logged exercises
        lex, lex_plan = [], []
        for s, (day, week) in zip(sessions, plan, strict=False):
            for order, slot in enumerate(day.slots.all().order_by("order")):
                le = LoggedExercise(session=s, exercise=slot.exercise, order=order)
                lex.append(le)
                lex_plan.append((slot.exercise.name, week))
        LoggedExercise.objects.bulk_create(lex)

        # logged sets — progressive overload + running-max PR detection
        best_e1rm: dict[str, float] = {}
        sets = []
        for le, (ename, week) in zip(lex, lex_plan, strict=False):
            base, inc = self.LIFTS.get(ename, (40, 0.5))
            bulk_weeks = min(week, 20)
            maint_weeks = max(0, week - 20)
            weight = base + inc * bulk_weeks + inc * 0.25 * maint_weeks
            weight += random.uniform(-inc, inc)  # day-to-day variability
            weight = max(base * 0.5, round(weight / 2.5) * 2.5)  # round to 2.5 kg
            # warm-up
            sets.append(LoggedSet(
                logged_exercise=le, order=0, set_type=SetType.WARMUP,
                reps=8, weight=Decimal(f"{round(weight*0.55/2.5)*2.5:.1f}"),
                rir=5, is_completed=True, e1rm=None, is_pr=False,
            ))
            for i in range(3):
                reps = random.randint(6, 10)
                w = weight - i * (round(weight * 0.03 / 2.5) * 2.5)  # slight back-off
                w = max(2.5, round(w / 2.5) * 2.5)
                e1 = round(w * (1 + reps / 30), 1)
                is_pr = e1 > best_e1rm.get(ename, 0) + 0.001
                if is_pr:
                    best_e1rm[ename] = e1
                sets.append(LoggedSet(
                    logged_exercise=le, order=i + 1, set_type=SetType.WORKING,
                    reps=reps, weight=Decimal(f"{w:.1f}"), rir=random.randint(1, 3),
                    is_completed=True, e1rm=Decimal(f"{e1:.1f}"), is_pr=is_pr,
                ))
        LoggedSet.objects.bulk_create(sets, batch_size=1000)
        self.stdout.write(f"Workouts: {len(sessions)} sessions, {len(sets)} sets")

    # ---- nutrition log -----------------------------------------------------
    MEAL_TEMPLATE = [
        ("Breakfast", [("Rolled oats, dry", 100), ("Whey protein powder", 30),
                       ("Banana", 120), ("Whole egg", 150)]),
        ("Lunch", [("Chicken breast, cooked", 250), ("White rice, cooked", 300),
                   ("Broccoli, cooked", 150), ("Olive oil", 15)]),
        ("Dinner", [("Salmon, cooked", 200), ("Sweet potato, baked", 300),
                    ("Broccoli, cooked", 150)]),
        ("Snack", [("Greek yogurt, nonfat", 200), ("Almonds", 30),
                   ("Whey protein powder", 30), ("Nutella", 20)]),
    ]

    def _template_kcal(self, refs):
        total = 0.0
        for _, items in self.MEAL_TEMPLATE:
            for fname, grams in items:
                food = refs["foods"].get(fname)
                fn = food and food.food_nutrients.filter(nutrient=refs["energy"]).first()
                if fn:
                    total += float(fn.amount_per_100g) * grams / 100.0
        return total or 3000.0

    def _target_for(self, d: date, targets):
        if d >= MAINT_START:
            return targets["Maintenance"]
        if d >= BULK_START + timedelta(weeks=14):
            return targets["Off-season surplus · phase 3"]
        if d >= BULK_START + timedelta(weeks=7):
            return targets["Off-season surplus · phase 2"]
        return targets["Off-season surplus · phase 1"]

    def _build_nutrition_log(self, user, refs, targets):
        from apps.nutrition.models import DiaryEntry, Meal
        tmpl_kcal = self._template_kcal(refs)
        meals, meal_keys = [], []
        for d in self._daterange(BULK_START, MAINT_END):
            if in_gap(d) and random.random() < 0.5:
                continue  # looser logging on holidays
            for order, (mname, _) in enumerate(self.MEAL_TEMPLATE):
                meals.append(Meal(owner=user, date=d, name=mname, order=order))
                meal_keys.append((d, mname))
        Meal.objects.bulk_create(meals)
        meal_by = {(m.date, m.name): m for m in meals}

        entries = []
        for d in {k[0] for k in meal_keys}:
            factor = float(self._target_for(d, targets).calories) / tmpl_kcal
            factor *= random.uniform(0.95, 1.06)
            for mname, items in self.MEAL_TEMPLATE:
                meal = meal_by.get((d, mname))
                if not meal:
                    continue
                for fname, grams in items:
                    food = refs["foods"].get(fname)
                    if not food:
                        continue
                    g = Decimal(f"{round(grams * factor)}")
                    entries.append(DiaryEntry(
                        owner=user, date=d, meal=meal, food=food, serving=None,
                        quantity=g, grams=g,  # grams==quantity when no serving
                    ))
        DiaryEntry.objects.bulk_create(entries, batch_size=1000)
        self.stdout.write(f"Nutrition: {len(meals)} meals, {len(entries)} entries")

    # ---- dose logs ---------------------------------------------------------
    def _build_doses(self, user, protocols, refs):
        from apps.protocols.models import DoseLog
        im_sites, subq_sites = refs["im_sites"], refs["subq_sites"]
        im_i = subq_i = 0
        rows = []
        for proto in (protocols["blast"], protocols["cruise"]):
            start = proto.started_on
            end = proto.ended_on
            for item in proto.items.all():
                for d in self._daterange(start, end):
                    if not self._due(item, d, start):
                        continue
                    gap = in_gap(d)
                    route = item.route
                    injectable = route in ("im", "subq")
                    skipped = bool(gap and "cold" in gap and injectable and random.random() < 0.5)
                    site = None
                    if route == "im" and im_sites:
                        site = im_sites[im_i % len(im_sites)]
                        im_i += 1
                    elif route == "subq" and subq_sites:
                        site = subq_sites[subq_i % len(subq_sites)]
                        subq_i += 1
                    hour = {"waking": 7, "am": 8, "noon": 13, "pm": 20, "night": 22}.get(
                        (item.times_of_day or ["am"])[0], 9)
                    rows.append(DoseLog(
                        owner=user, protocol_item=item,
                        compound=item.compound, supplement=item.supplement,
                        taken_at=self._dt(d, hour, random.choice([0, 10, 20])),
                        amount=item.dose_amount or Decimal("1"), unit=item.dose_unit, route=route,
                        injection_site=site,
                        status="skipped" if skipped else "taken",
                        notes="Missed — unwell" if skipped else "",
                    ))
        DoseLog.objects.bulk_create(rows, batch_size=1000)
        self.stdout.write(f"Doses: {len(rows)}")

    def _due(self, item, d: date, start: date) -> bool:
        freq = item.frequency
        if freq == "daily":
            return True
        if freq == "eod":
            return (d - start).days % 2 == 0
        if freq == "every_3_days":
            return (d - start).days % 3 == 0
        if freq == "weekly":
            return d.weekday() == start.weekday()
        if freq == "specific_days":
            return d.weekday() in (item.days_of_week or [])
        return False

    # ---- body measurements -------------------------------------------------
    def _build_measurements(self, user):
        from apps.analysis.models import BodyFatMethod, BodyMeasurement, MeasurementType
        rows = []
        # (type, bulk start→end, maintenance end value)
        specs = [
            (MeasurementType.WAIST, 80, 95, 93),
            (MeasurementType.CHEST, 108, 122, 121),
            (MeasurementType.UPPER_ARM_LEFT, 38, 43.5, 43),
            (MeasurementType.UPPER_ARM_RIGHT, 38.3, 43.8, 43.3),
            (MeasurementType.THIGH_LEFT, 60, 67, 66.5),
            (MeasurementType.THIGH_RIGHT, 60.2, 67.2, 66.7),
            (MeasurementType.BODY_FAT, 12.5, 18.5, 16.5),
        ]
        for d in self._daterange(BULK_START, MAINT_END):
            if d.weekday() != 6 or (d.toordinal() // 7) % 2:  # every other Sunday
                continue
            for mtype, b0, b1, m1 in specs:
                if d <= BULK_END:
                    frac = (d - BULK_START).days / (BULK_END - BULK_START).days
                    val = b0 + (b1 - b0) * frac
                else:
                    frac = (d - MAINT_START).days / (MAINT_END - MAINT_START).days
                    val = b1 + (m1 - b1) * frac
                val += random.uniform(-0.3, 0.3)
                rows.append(BodyMeasurement(
                    owner=user, date=d, type=mtype, value=Decimal(f"{val:.1f}"),
                    method=BodyFatMethod.CALIPERS if mtype == MeasurementType.BODY_FAT else "",
                ))
        BodyMeasurement.objects.bulk_create(rows, batch_size=500)
        self.stdout.write(f"Measurements: {len(rows)}")

    # ---- bloodwork ---------------------------------------------------------
    # Comprehensive panel: (marker slug, off-cycle "normal", on-blast "peak").
    # Each panel interpolates between them by a per-panel cycle intensity, so the
    # whole picture trends realistically — androgens up, gonadotropins/HDL down,
    # hematocrit/IGF-1/CK up, liver mildly up, recovering on the cruise.
    BLOOD_MARKERS = [
        # Sex hormones
        ("testosterone", 22, 48), ("free-testosterone", 0.45, 1.05),
        ("estradiol-e2", 110, 150), ("shbg", 32, 16), ("lh", 4.5, 0.2),
        ("fsh", 4.0, 0.3), ("prolactin", 180, 300), ("progesteron", 1.4, 2.6),
        ("dhea-s", 8.0, 7.0), ("igf-1", 22, 52), ("psa", 0.8, 1.2),
        # Thyroid / adrenal
        ("tsh-basal", 1.8, 1.5), ("free-t3", 5.0, 4.7), ("free-t4", 16, 15),
        ("cortisol", 360, 300),
        # Lipids
        ("total-cholesterol", 4.3, 5.6), ("hdl", 1.3, 0.62), ("ldl", 2.6, 4.0),
        ("non-hdl-cholesterol", 3.0, 4.9), ("triglycerides", 1.1, 1.9),
        ("apolipoprotein-a-i", 1.5, 1.1), ("apolipoprotein-b", 0.85, 1.25),
        # Liver
        ("asat", 28, 55), ("alat", 30, 62), ("ggt", 24, 48),
        ("bilirubin", 9, 13), ("bilirubin-direct", 2.0, 2.8),
        # Kidney
        ("creatinine", 88, 109), ("gfr", 100, 86),
        # Hematology (full count + iron studies)
        ("leucocytes", 6.0, 6.6), ("erythrocytes", 5.1, 5.9), ("hemoglobin", 9.6, 11.4),
        ("hematocrit", 0.45, 0.53), ("mcv", 89, 90), ("mch", 1.85, 1.9),
        ("mchc", 21.0, 21.4), ("rdw", 13.0, 13.6), ("thrombocytes", 250, 235),
        ("neutrophils", 55, 58), ("lymphocytes", 32, 29), ("monocytes", 7, 7),
        ("eosinophils", 2.5, 2.0), ("basophils", 0.5, 0.5), ("ferritin", 150, 85),
        ("iron", 18, 15), ("transferrin", 2.6, 2.8), ("transferrin-saturation", 30, 23),
        # Metabolic + minerals
        ("blood-glucose-fasted", 5.0, 5.4), ("hba1c", 5.1, 5.5), ("hba1c-ifcc", 32, 37),
        ("ck", 180, 430), ("magnesium", 0.88, 0.84), ("sodium", 140, 141),
        ("potassium", 4.4, 4.5), ("albumin", 45, 46),
        # Vitamins + inflammation
        ("25-hydroxy-vitamin-d", 80, 118), ("vitamin-b12", 350, 480), ("crp", 1.2, 2.6),
    ]

    def _build_bloodwork(self, user):
        from apps.protocols.models import BloodMarker, BloodResult

        markers = {m.slug: m for m in BloodMarker.objects.all()}
        # Comprehensive panels every ~6–7 weeks across the 32 weeks.
        panels = [
            (BULK_START + timedelta(weeks=1), 0.80, "Baseline / early blast"),
            (BULK_START + timedelta(weeks=8), 1.00, "Mid-blast panel"),
            (BULK_START + timedelta(weeks=15), 1.00, "Blast week 15"),
            (BULK_END - timedelta(days=4), 0.95, "End-of-blast panel"),
            (MAINT_START + timedelta(weeks=6), 0.45, "Mid-cruise recovery"),
            (MAINT_END - timedelta(days=4), 0.20, "End-of-cruise panel"),
        ]

        def rnd(v):
            a = abs(v)
            if a >= 50:
                return round(v)
            if a >= 1:
                return round(v, 1)
            return round(v, 3)

        rows = []
        for d, intensity, note in panels:
            for slug, normal, peak in self.BLOOD_MARKERS:
                m = markers.get(slug)
                if not m:
                    continue
                val = normal + (peak - normal) * intensity
                val += random.gauss(0, max(abs(normal), 0.1) * 0.02)
                rows.append(BloodResult(
                    owner=user, marker=m, value=Decimal(str(rnd(val))),
                    measured_on=d, source="manual", notes=note,
                ))
        BloodResult.objects.bulk_create(rows, batch_size=1000)
        self.stdout.write(f"Bloodwork: {len(rows)} results across {len(panels)} panels")

    # ---- progress photos ---------------------------------------------------
    def _photo_source_dates(self):
        """Map on-disk folder dates onto the bulk window, preserving relative spacing.

        Folders carry their real shoot dates, which won't line up with a timeline
        anchored to *today*, so the real sequence is scaled onto
        [BULK_START, BULK_END]. Any large trailing gap before the most-recent
        shots is collapsed to a week, so those read as the final weeks of the bulk.
        """
        if not self.photos_dir.exists():
            return {}
        folders = []
        for sub in self.photos_dir.iterdir():
            if not sub.is_dir():
                continue
            try:
                folders.append((datetime.strptime(sub.name, "%Y-%m-%d").date(), sub))
            except ValueError:
                continue
        if not folders:
            return {}
        folders.sort(key=lambda t: t[0])
        # Source timeline: real dates, collapsing any gap > 5 weeks to one week.
        source = []
        for real, sub in folders:
            src_date = source[-1][0] + timedelta(weeks=1) \
                if source and (real - source[-1][1]).days > 35 else real
            source.append((src_date, real, sub))
        lo, hi = source[0][0], source[-1][0]
        span = max((hi - lo).days, 1)
        win = max((BULK_END - BULK_START).days, 1)
        return {
            sub: BULK_START + timedelta(days=round((src - lo).days / span * win))
            for src, _real, sub in source
        }

    def _photo_dates(self):
        return set(self._photo_source_dates().values())

    def _build_photos(self, user):
        from apps.diary.images import make_thumbnail, process_image
        from apps.diary.models import ProgressPhoto
        from apps.diary.storage import get_storage

        sources = self._photo_source_dates()
        if not sources:
            self.stdout.write(self.style.WARNING(
                f"No photos found under {self.photos_dir} — skipping photos."))
            return 0
        storage = get_storage()
        try:
            storage.ensure_bucket()
        except Exception:
            pass
        poses = self._load_refs()["poses"]
        created = 0
        for sub, demo_date in sorted(sources.items(), key=lambda kv: kv[1]):
            for prefix, pose_slug in POSE_FILES.items():
                match = next((f for f in sorted(sub.iterdir())
                              if f.is_file() and f.name.lower().startswith(prefix + "_")
                              and f.suffix.lower() in IMAGE_EXTS), None)
                if not match:
                    continue
                raw = match.read_bytes()
                try:
                    jpeg, w, h = process_image(raw)
                    thumb = make_thumbnail(raw)
                except Exception as exc:  # pragma: no cover
                    self.stdout.write(self.style.WARNING(f"  skip {match.name}: {exc}"))
                    continue
                base = f"demo/{user.id}/{demo_date.isoformat()}/{pose_slug}-{uuid.uuid4().hex[:8]}"
                object_key, thumb_key = f"{base}.jpg", f"{base}-thumb.jpg"
                storage.put(object_key, jpeg, "image/jpeg")
                storage.put(thumb_key, thumb, "image/jpeg")
                ProgressPhoto.objects.create(
                    owner=user, pose=poses.get(pose_slug), taken_on=demo_date,
                    object_key=object_key, thumb_key=thumb_key, content_type="image/jpeg",
                    width=w, height=h, bytes=len(jpeg),
                    notes="Off-season weekly check-in",
                )
                created += 1
        self.stdout.write(f"Photos: {created}")
        return created
