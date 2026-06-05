"""Seed reference data for the protocols module (idempotent).

Run:  python manage.py seed_protocols

Contains ONLY factual reference constants — compound pharmacokinetics (elimination
half-life, ester active fraction), canonical injection sites, and lab-marker
reference ranges. It does NOT contain or imply any dose recommendation. BBTracker
is a personal tracker, not medical advice.

Sources for half-lives/active fractions are standard pharmacology references; values
are approximate and provided for the user's own concentration-curve visualisation.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.protocols.enums import CompoundClass, DoseUnit, MarkerCategory, Route, Side
from apps.protocols.models import BloodMarker, Compound, InjectionSite

CC = CompoundClass

# name, class, default_unit, default_route, half_life_hours, ester, active_fraction
COMPOUNDS = [
    # Anabolics (ester active fraction = free steroid / ester weight)
    ("Testosterone Enanthate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "168", "Enanthate", "0.700"),
    ("Testosterone Cypionate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "192", "Cypionate", "0.690"),
    ("Testosterone Propionate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "20", "Propionate", "0.800"),
    ("Testosterone Undecanoate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "504", "Undecanoate", "0.630"),
    ("Nandrolone Decanoate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "144", "Decanoate", "0.640"),
    ("Trenbolone Acetate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "24", "Acetate", "0.870"),
    ("Boldenone Undecylenate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "336", "Undecylenate", "0.620"),
    ("Masteron (Drostanolone Propionate)", CC.ANABOLIC, DoseUnit.MG, Route.IM, "48",
     "Propionate", "0.800"),
    ("Oxandrolone (Anavar)", CC.ANABOLIC, DoseUnit.MG, Route.ORAL, "9", "", "1.000"),
    # Peptides
    ("BPC-157", CC.PEPTIDE, DoseUnit.MCG, Route.SUBQ, "4", "", "1.000"),
    ("Ipamorelin", CC.PEPTIDE, DoseUnit.MCG, Route.SUBQ, "2", "", "1.000"),
    ("CJC-1295 (no DAC)", CC.PEPTIDE, DoseUnit.MCG, Route.SUBQ, "0.5", "", "1.000"),
    ("Semaglutide", CC.PEPTIDE, DoseUnit.MG, Route.SUBQ, "168", "", "1.000"),
    ("Tesamorelin", CC.PEPTIDE, DoseUnit.MG, Route.SUBQ, "0.6", "", "1.000"),
    # Ancillaries / pharmaceuticals
    ("Anastrozole", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "48", "", "1.000"),
    ("Exemestane", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "24", "", "1.000"),
    ("Tamoxifen", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "120", "", "1.000"),
    ("Enclomiphene", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "240", "", "1.000"),
    ("hCG", CC.ANCILLARY, DoseUnit.IU, Route.SUBQ, "33", "", "1.000"),
    ("Telmisartan", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "24", "", "1.000"),
    ("Isotretinoin", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "21", "", "1.000"),
    ("Finasteride", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "6", "", "1.000"),
    ("Cialis (Tadalafil)", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "17.5", "", "1.000"),
    ("Metformin", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "6", "", "1.000"),
]

# region, side, x%, y% (front-facing body map viewbox 0..100)
SITES = [
    ("Left ventroglute", "ventroglute", Side.LEFT, "38", "52"),
    ("Right ventroglute", "ventroglute", Side.RIGHT, "62", "52"),
    ("Left glute", "glute", Side.LEFT, "40", "56"),
    ("Right glute", "glute", Side.RIGHT, "60", "56"),
    ("Left quad", "quad", Side.LEFT, "42", "70"),
    ("Right quad", "quad", Side.RIGHT, "58", "70"),
    ("Left delt", "delt", Side.LEFT, "30", "30"),
    ("Right delt", "delt", Side.RIGHT, "70", "30"),
    ("Left pec", "pec", Side.LEFT, "43", "32"),
    ("Right pec", "pec", Side.RIGHT, "57", "32"),
    ("Left abdomen (SubQ)", "abdomen", Side.LEFT, "45", "46"),
    ("Right abdomen (SubQ)", "abdomen", Side.RIGHT, "55", "46"),
]

# name, unit, category, ref_low, ref_high, ref_low_male, ref_high_male,
# ref_low_female, ref_high_female, order
MARKERS = [
    # --- Complete blood count ---
    ("Leucocytes", "10³/µL", MarkerCategory.BLOOD, 3.9, 10.2, None, None, None, None, 10),
    ("Erythrocytes", "10⁶/µL", MarkerCategory.BLOOD, None, None, 4.3, 5.7, 3.9, 5.0, 11),
    ("Hemoglobin", "g/dL", MarkerCategory.BLOOD, None, None, 13.5, 17.5, 12.0, 15.5, 12),
    ("Hematocrit", "%", MarkerCategory.BLOOD, None, None, 38.8, 50.0, 34.9, 44.5, 13),
    ("MCV", "fL", MarkerCategory.BLOOD, 80, 100, None, None, None, None, 14),
    ("MCH", "pg", MarkerCategory.BLOOD, 27, 33, None, None, None, None, 15),
    ("MCHC", "g/dL", MarkerCategory.BLOOD, 32, 36, None, None, None, None, 16),
    ("RDW", "%", MarkerCategory.BLOOD, 11.5, 14.5, None, None, None, None, 17),
    ("Thrombocytes", "10³/µL", MarkerCategory.BLOOD, 150, 400, None, None, None, None, 18),
    ("Neutrophils", "%", MarkerCategory.BLOOD, 40, 70, None, None, None, None, 19),
    ("Eosinophils", "%", MarkerCategory.BLOOD, 0, 6, None, None, None, None, 20),
    ("Basophils", "%", MarkerCategory.BLOOD, 0, 2, None, None, None, None, 21),
    ("Lymphocytes", "%", MarkerCategory.BLOOD, 20, 45, None, None, None, None, 22),
    ("Monocytes", "%", MarkerCategory.BLOOD, 2, 10, None, None, None, None, 23),
    # --- Iron status ---
    ("Ferritin", "ng/mL", MarkerCategory.BLOOD, None, None, 30, 400, 13, 150, 30),
    ("Transferrin", "mg/dL", MarkerCategory.BLOOD, 200, 360, None, None, None, None, 31),
    ("Transferrin saturation", "%", MarkerCategory.BLOOD, 20, 50, None, None, None, None, 32),
    ("Iron", "µg/dL", MarkerCategory.BLOOD, None, None, 65, 176, 50, 170, 33),
    # --- Liver ---
    ("Bilirubin", "mg/dL", MarkerCategory.LIVER, 0.1, 1.2, None, None, None, None, 40),
    ("ASAT", "U/L", MarkerCategory.LIVER, None, None, 0, 40, 0, 32, 41),
    ("ALAT", "U/L", MarkerCategory.LIVER, None, None, 0, 50, 0, 35, 42),
    ("gGT", "U/L", MarkerCategory.LIVER, None, None, 0, 60, 0, 40, 43),
    # --- Lipids ---
    ("Total Cholesterol", "mg/dL", MarkerCategory.LIPID, 0, 200, None, None, None, None, 50),
    ("HDL", "mg/dL", MarkerCategory.LIPID, None, None, 40, None, 50, None, 51),
    ("LDL", "mg/dL", MarkerCategory.LIPID, 0, 116, None, None, None, None, 52),
    ("Triglycerides", "mg/dL", MarkerCategory.LIPID, 0, 150, None, None, None, None, 53),
    ("Apolipoprotein A-I", "mg/dL", MarkerCategory.LIPID, None, None, 110, 180, 110, 205, 54),
    ("Apolipoprotein B", "mg/dL", MarkerCategory.LIPID, 0, 100, None, None, None, None, 55),
    # --- Glucose metabolism ---
    ("Blood Glucose (fasted)", "mg/dL", MarkerCategory.METABOLIC, 70, 99, None, None, None, None, 60),
    ("HbA1c", "%", MarkerCategory.METABOLIC, 4.0, 5.6, None, None, None, None, 61),
    ("HbA1c (IFCC)", "mmol/mol", MarkerCategory.METABOLIC, 20, 38, None, None, None, None, 62),
    ("HbA1c - Plasma glucose", "mg/dL", MarkerCategory.METABOLIC, 70, 114, None, None, None, None, 63),
    # --- Renal / muscle ---
    ("Creatinine", "mg/dL", MarkerCategory.KIDNEY, None, None, 0.7, 1.3, 0.6, 1.1, 70),
    ("GFR", "mL/min/1.73m²", MarkerCategory.KIDNEY, 90, 200, None, None, None, None, 71),
    ("CK", "U/L", MarkerCategory.METABOLIC, None, None, 39, 308, 26, 192, 72),
    # --- Electrolytes ---
    ("Magnesium", "mg/dL", MarkerCategory.METABOLIC, 1.7, 2.2, None, None, None, None, 80),
    ("Sodium", "mmol/L", MarkerCategory.METABOLIC, 135, 145, None, None, None, None, 81),
    ("Potassium", "mmol/L", MarkerCategory.METABOLIC, 3.5, 5.1, None, None, None, None, 82),
    # --- Vitamins ---
    ("25-hydroxy-vitamin D", "ng/mL", MarkerCategory.OTHER, 30, 100, None, None, None, None, 90),
    ("Vitamin B12", "pg/mL", MarkerCategory.OTHER, 200, 900, None, None, None, None, 91),
    # --- Inflammation / protein ---
    ("CRP", "mg/L", MarkerCategory.OTHER, 0, 5, None, None, None, None, 100),
    ("Albumin", "g/dL", MarkerCategory.METABOLIC, 3.5, 5.0, None, None, None, None, 101),
    # --- Thyroid ---
    ("TSH (basal)", "mIU/L", MarkerCategory.HORMONE, 0.4, 4.0, None, None, None, None, 110),
    ("Free T3", "pg/mL", MarkerCategory.HORMONE, 2.3, 4.2, None, None, None, None, 111),
    ("Free T4", "ng/dL", MarkerCategory.HORMONE, 0.8, 1.8, None, None, None, None, 112),
    # --- Sex / anabolic hormones ---
    ("LH", "mIU/mL", MarkerCategory.HORMONE, None, None, 1.7, 8.6, 1.0, 95, 120),
    ("FSH", "mIU/mL", MarkerCategory.HORMONE, None, None, 1.5, 12.4, 1.0, 150, 121),
    ("Estradiol (E2)", "pg/mL", MarkerCategory.HORMONE, None, None, 10, 40, 15, 350, 122),
    ("Prolactin", "ng/mL", MarkerCategory.HORMONE, None, None, 4, 15, 4, 30, 123),
    ("Testosterone", "ng/dL", MarkerCategory.HORMONE, None, None, 300, 1000, 15, 70, 124),
    ("Free Testosterone", "pg/mL", MarkerCategory.HORMONE, None, None, 50, 210, 1.0, 8.5, 125),
    ("SHBG", "nmol/L", MarkerCategory.HORMONE, None, None, 10, 57, 18, 144, 126),
    ("IGF-1", "ng/mL", MarkerCategory.HORMONE, 88, 240, None, None, None, None, 127),
    ("Cortisol", "µg/dL", MarkerCategory.HORMONE, 6, 23, None, None, None, None, 128),
    ("Progesteron", "ng/mL", MarkerCategory.HORMONE, None, None, 0.2, 1.4, 0.1, 25, 129),
    ("DHEA-S", "µg/dL", MarkerCategory.HORMONE, None, None, 80, 560, 35, 430, 130),
    ("PSA", "ng/mL", MarkerCategory.HORMONE, 0, 4.0, None, None, None, None, 131),
]


def _dec(v):
    return None if v is None else Decimal(str(v))


class Command(BaseCommand):
    help = "Seed compounds, injection sites, and blood markers (idempotent, reference data only)."

    @transaction.atomic
    def handle(self, *args, **options):
        c_new = 0
        for name, cls, unit, route, half_life, ester, active in COMPOUNDS:
            _, created = Compound.objects.update_or_create(
                owner=None,
                name=name,
                defaults={
                    "slug": slugify(name),
                    "compound_class": cls,
                    "default_unit": unit,
                    "default_route": route,
                    "half_life_hours": Decimal(half_life),
                    "ester": ester,
                    "active_fraction": Decimal(active),
                },
            )
            c_new += created

        for name, region, side, x, y in SITES:
            InjectionSite.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name, "region": region, "side": side,
                    "x": Decimal(x), "y": Decimal(y),
                },
            )

        m_new = 0
        for (name, unit, cat, lo, hi, lom, him, lof, hif, order) in MARKERS:
            _, created = BloodMarker.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name, "unit": unit, "category": cat,
                    "ref_low": _dec(lo), "ref_high": _dec(hi),
                    "ref_low_male": _dec(lom), "ref_high_male": _dec(him),
                    "ref_low_female": _dec(lof), "ref_high_female": _dec(hif),
                    "display_order": order,
                },
            )
            m_new += created

        # Drop superseded reference markers that carry no user data (keeps the
        # catalogue tidy across seed revisions; PROTECT keeps any with results).
        desired = {slugify(name) for name, *_rest in MARKERS}
        BloodMarker.objects.exclude(slug__in=desired).filter(results__isnull=True).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(COMPOUNDS)} compounds ({c_new} new), "
                f"{len(SITES)} injection sites, {len(MARKERS)} blood markers ({m_new} new)."
            )
        )
