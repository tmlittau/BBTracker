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

# name, class, default_unit, default_route, half_life_hours, ester, active_fraction,
# tmax_hours, bioavailability, pk_source
# Half-life / Tmax / bioavailability (and their sources) come from the steroidplotter PK
# dataset's cited studies; "" = unknown (the concentration model then falls back to
# instantaneous absorption). Active fractions are ester/salt weight corrections.
COMPOUNDS = [
    # Anabolics (ester active fraction = free steroid / ester weight)
    ("Testosterone Enanthate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "172.6", "Enanthate", "0.700",
     "33.3", "0.72", "Yin et al. 2014 (PMC4721027)"),
    ("Testosterone Cypionate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "165.6", "Cypionate", "0.690",
     "108", "0.70", "psp4.12287 / ajpendo.00502.2001"),
    ("Testosterone Propionate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "24.9", "Propionate", "0.800",
     "25.5", "0.84", "JCEM 63/6/1361"),
    ("Testosterone Undecanoate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "813.6",
     "Undecanoate", "0.630", "240", "0.65", "Nebido PI / jandrol.109.009597"),
    ("Nandrolone Decanoate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "244.8", "Decanoate", "0.640",
     "44", "0.73", "JCEM 90/5/2624"),
    ("Trenbolone Acetate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "36", "Acetate", "0.870",
     "", "0.87", "ScienceDirect S002228602030452X"),
    ("Boldenone Undecylenate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "123", "Undecylenate", "0.620",
     "144", "0.63", "pubmed 17348894"),
    ("Masteron (Drostanolone Propionate)", CC.ANABOLIC, DoseUnit.MG, Route.IM, "48",
     "Propionate", "0.800", "", "0.84", "Llewellyn, Anabolics 2011"),
    ("Oxandrolone (Anavar)", CC.ANABOLIC, DoseUnit.MG, Route.ORAL, "6.7", "", "1.000",
     "1.6", "0.625", "PMC7134583"),
    # Anabolics — extended roster (PK from the steroidplotter dataset's cited studies)
    ("Testosterone Suspension", CC.ANABOLIC, DoseUnit.MG, Route.IM, "33", "", "1.000",
     "6", "1.0", "RMTC equine PK (interlaboratory)"),
    ("Nandrolone Phenylpropionate (NPP)", CC.ANABOLIC, DoseUnit.MG, Route.IM, "57.6",
     "Phenylpropionate", "0.670", "24", "0.67", "pubmed 9103484"),
    ("Trenbolone Enanthate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "264", "Enanthate", "0.700",
     "", "0.71", "ScienceDirect S002228602030452X"),
    ("Trenbolone Hexahydrobenzylcarbonate", CC.ANABOLIC, DoseUnit.MG, Route.IM, "192",
     "Hexahydrobenzylcarbonate", "0.650", "", "0.66", "ScienceDirect S002228602030452X"),
    ("Masteron Enanthate (Drostanolone Enanthate)", CC.ANABOLIC, DoseUnit.MG, Route.IM, "108",
     "Enanthate", "0.710", "", "0.73", "Llewellyn, Anabolics 2011"),
    ("Primobolan (Methenolone Enanthate)", CC.ANABOLIC, DoseUnit.MG, Route.IM, "252",
     "Enanthate", "0.720", "", "0.73", "Vida, Androgens & Anabolic Agents"),
    ("Primobolan (Methenolone Acetate, oral)", CC.ANABOLIC, DoseUnit.MG, Route.ORAL, "5",
     "", "1.000", "", "0.88", "numerous sources"),
    ("Dihydroboldenone (DHB)", CC.ANABOLIC, DoseUnit.MG, Route.IM, "216", "", "1.000",
     "", "1.0", "numerous sources"),
    ("Methandrostenolone (Dianabol)", CC.ANABOLIC, DoseUnit.MG, Route.ORAL, "5.25", "", "1.000",
     "", "0.95", "bionity.com encyclopedia"),
    ("Oxymetholone (Anadrol)", CC.ANABOLIC, DoseUnit.MG, Route.ORAL, "8", "", "1.000",
     "3.5", "0.95", "Validation of oxymetholone GC-MS PK"),
    ("Stanozolol (Winstrol, oral)", CC.ANABOLIC, DoseUnit.MG, Route.ORAL, "9", "", "1.000",
     "", "1.0", "Vida, Androgens & Anabolic Agents"),
    ("Stanozolol (Winstrol, injectable)", CC.ANABOLIC, DoseUnit.MG, Route.IM, "82", "", "1.000",
     "168", "1.0", "pubmed 17348894"),
    ("Turinabol", CC.ANABOLIC, DoseUnit.MG, Route.ORAL, "16", "", "1.000",
     "", "1.0", "pubmed 1798729"),
    ("Methasterone (Superdrol)", CC.ANABOLIC, DoseUnit.MG, Route.ORAL, "10", "", "1.000",
     "", "0.5", "Wikipedia: Methasterone"),
    ("Mesterolone (Proviron)", CC.ANABOLIC, DoseUnit.MG, Route.ORAL, "12.5", "", "1.000",
     "1.6", "0.03", "Bayer Proviron PI"),
    # Peptides
    ("BPC-157", CC.PEPTIDE, DoseUnit.MCG, Route.SUBQ, "4", "", "1.000", "", "", ""),
    ("Ipamorelin", CC.PEPTIDE, DoseUnit.MCG, Route.SUBQ, "2", "", "1.000", "", "", ""),
    ("CJC-1295 (no DAC)", CC.PEPTIDE, DoseUnit.MCG, Route.SUBQ, "0.5", "", "1.000", "", "", ""),
    ("Semaglutide", CC.PEPTIDE, DoseUnit.MG, Route.SUBQ, "156", "", "1.000",
     "30", "0.89", "PMC7854449"),
    ("Tesamorelin", CC.PEPTIDE, DoseUnit.MG, Route.SUBQ, "0.6", "", "1.000", "", "", ""),
    # Ancillaries / pharmaceuticals
    ("Anastrozole", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "46.8", "", "1.000",
     "1.0", "0.80", "pubmed 19470631"),
    ("Exemestane", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "22.7", "", "1.000",
     "1.4", "0.05", "PMC1884784"),
    ("Tamoxifen", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "47.4", "", "1.000",
     "8.3", "0.15", "Nolvadex FDA biopharmr"),
    ("Enclomiphene", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "240", "", "1.000", "", "", ""),
    ("hCG", CC.ANCILLARY, DoseUnit.IU, Route.SUBQ, "47.1", "", "1.000",
     "24", "0.45", "PMC8301557"),
    ("Telmisartan", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "23.3", "", "1.000",
     "1.7", "0.43", "pubmed 17009837"),
    ("Isotretinoin", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "21", "", "1.000", "", "", ""),
    ("Finasteride", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "6", "", "1.000", "", "", ""),
    ("Cialis (Tadalafil)", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "17", "", "1.000",
     "2.5", "", "PMC1885023"),
    ("Metformin", CC.ANCILLARY, DoseUnit.MG, Route.ORAL, "6", "", "1.000", "", "", ""),
]

# name, region, side, route, x%, y% (body-map viewbox 0..100). Route drives the
# route-filtered site picker; x/y position the dot on the body-map fallback.
SITES = [
    # Intramuscular
    ("Left pec", "pec", Side.LEFT, Route.IM, "43", "32"),
    ("Right pec", "pec", Side.RIGHT, Route.IM, "57", "32"),
    ("Left lat", "lats", Side.LEFT, Route.IM, "34", "44"),
    ("Right lat", "lats", Side.RIGHT, Route.IM, "66", "44"),
    ("Left front delt", "front_delt", Side.LEFT, Route.IM, "35", "29"),
    ("Right front delt", "front_delt", Side.RIGHT, Route.IM, "65", "29"),
    ("Left rear delt", "rear_delt", Side.LEFT, Route.IM, "30", "28"),
    ("Right rear delt", "rear_delt", Side.RIGHT, Route.IM, "70", "28"),
    ("Left glute", "glute", Side.LEFT, Route.IM, "40", "56"),
    ("Right glute", "glute", Side.RIGHT, Route.IM, "60", "56"),
    ("Left quad", "quad", Side.LEFT, Route.IM, "42", "70"),
    ("Right quad", "quad", Side.RIGHT, Route.IM, "58", "70"),
    # Subcutaneous
    ("Left glute (SubQ)", "glute", Side.LEFT, Route.SUBQ, "41", "57"),
    ("Right glute (SubQ)", "glute", Side.RIGHT, Route.SUBQ, "59", "57"),
    ("Left lower back", "lower_back", Side.LEFT, Route.SUBQ, "40", "49"),
    ("Right lower back", "lower_back", Side.RIGHT, Route.SUBQ, "60", "49"),
    ("Left lower belly", "lower_belly", Side.LEFT, Route.SUBQ, "45", "46"),
    ("Right lower belly", "lower_belly", Side.RIGHT, Route.SUBQ, "55", "46"),
]

# name, unit, category, ref_low, ref_high, ref_low_male, ref_high_male,
# ref_low_female, ref_high_female, order, aliases
# Units are SI (the app's reference convention, matching EU/NL lab reports); ranges
# follow SI norms / the user's lab. `aliases` are lab/Dutch synonyms used to match a
# marker when importing a PDF (matched case/accent-insensitively against name+aliases).
MARKERS = [
    # --- Complete blood count ---
    ("Leucocytes", "10⁹/L", MarkerCategory.BLOOD, 4.2, 9.1, None, None, None, None, 10,
     ["leucocyten", "leukocyten", "leukocytes", "wbc"]),
    ("Erythrocytes", "10¹²/L", MarkerCategory.BLOOD, None, None, 4.6, 6.1, 3.9, 5.1, 11,
     ["erythrocyten", "erytrocyten", "rbc", "red blood cells"]),
    ("Hemoglobin", "mmol/L", MarkerCategory.BLOOD, None, None, 8.5, 10.9, 7.5, 9.9, 12,
     ["hemoglobine", "haemoglobin", "hb"]),
    ("Hematocrit", "L/L", MarkerCategory.BLOOD, None, None, 0.41, 0.52, 0.36, 0.46, 13,
     ["hematocriet", "haematocrit", "ht", "hct"]),
    ("MCV", "fL", MarkerCategory.BLOOD, 82, 98, None, None, None, None, 14, ["mcv"]),
    ("MCH", "fmol", MarkerCategory.BLOOD, 1.59, 2.00, None, None, None, None, 15, ["mch"]),
    ("MCHC", "mmol/L", MarkerCategory.BLOOD, 19.0, 22.5, None, None, None, None, 16, ["mchc"]),
    ("RDW", "%", MarkerCategory.BLOOD, 11.0, 16.0, None, None, None, None, 17, ["rdw", "rdw-cv"]),
    ("Thrombocytes", "10⁹/L", MarkerCategory.BLOOD, 150, 400, None, None, None, None, 18,
     ["thrombocyten", "trombocyten", "platelets", "plt"]),
    ("Neutrophils", "%", MarkerCategory.BLOOD, 40, 70, None, None, None, None, 19,
     ["neutrofielen", "neutrophils", "neutro"]),
    ("Eosinophils", "%", MarkerCategory.BLOOD, 0, 6, None, None, None, None, 20,
     ["eosinofielen", "eosinophils", "eos"]),
    ("Basophils", "%", MarkerCategory.BLOOD, 0, 2, None, None, None, None, 21,
     ["basofielen", "basophils", "baso"]),
    ("Lymphocytes", "%", MarkerCategory.BLOOD, 20, 45, None, None, None, None, 22,
     ["lymfocyten", "lymphocytes", "lymfo"]),
    ("Monocytes", "%", MarkerCategory.BLOOD, 2, 10, None, None, None, None, 23,
     ["monocyten", "monocytes", "mono"]),
    # --- Iron status ---
    ("Ferritin", "µg/L", MarkerCategory.BLOOD, None, None, 30, 400, 13, 150, 30,
     ["ferritine", "ferritin"]),
    ("Transferrin", "g/L", MarkerCategory.BLOOD, 2.0, 3.6, None, None, None, None, 31,
     ["transferrine", "transferrin"]),
    ("Transferrin saturation", "%", MarkerCategory.BLOOD, 16.0, 45.0, None, None, None, None, 32,
     ["transferrine saturatie", "transferrin saturation", "tsat", "ijzerverzadiging"]),
    ("Iron", "µmol/L", MarkerCategory.BLOOD, 5.9, 34.5, None, None, None, None, 33,
     ["ijzer", "iron", "fe"]),
    # --- Liver ---
    ("Bilirubin", "µmol/L", MarkerCategory.LIVER, 0, 21, None, None, None, None, 40,
     ["bilirubine", "bilirubine totaal", "totaal bilirubine", "total bilirubin"]),
    ("Bilirubin (direct)", "µmol/L", MarkerCategory.LIVER, 0, 3.4, None, None, None, None, 41,
     ["bilirubine direct", "direct bilirubin", "geconjugeerd bilirubine"]),
    ("ASAT", "U/L", MarkerCategory.LIVER, 0, 50, None, None, None, None, 42,
     ["asat", "asat (got)", "got", "ast", "aspartaataminotransferase"]),
    ("ALAT", "U/L", MarkerCategory.LIVER, 0, 50, None, None, None, None, 43,
     ["alat", "alat (gpt)", "gpt", "alt", "alanineaminotransferase"]),
    ("gGT", "U/L", MarkerCategory.LIVER, 0, 60, None, None, None, None, 44,
     ["gamma-gt", "gamma gt", "ggt", "y-gt", "gamma-glutamyltransferase"]),
    # --- Lipids (SI: mmol/L) ---
    ("Total Cholesterol", "mmol/L", MarkerCategory.LIPID, 0, 5.18, None, None, None, None, 50,
     ["cholesterol", "totaal cholesterol", "total cholesterol"]),
    ("HDL", "mmol/L", MarkerCategory.LIPID, 0.91, 2.07, None, None, None, None, 51,
     ["hdl-cholesterol", "hdl"]),
    ("LDL", "mmol/L", MarkerCategory.LIPID, 0, 3.37, None, None, None, None, 52,
     ["ldl-cholesterol", "ldl"]),
    ("Non-HDL-Cholesterol", "mmol/L", MarkerCategory.LIPID, None, None, None, None, None, None, 53,
     ["non-hdl-cholesterol", "non-hdl", "non hdl cholesterol"]),
    ("Triglycerides", "mmol/L", MarkerCategory.LIPID, 0, 2.28, None, None, None, None, 54,
     ["triglyceriden", "triglycerides", "tg", "trig"]),
    ("Apolipoprotein A-I", "g/L", MarkerCategory.LIPID, 1.04, 2.02, None, None, None, None, 55,
     ["apolipoproteine a-i", "apolipoproteine a1", "apo a-i", "apoa1"]),
    ("Apolipoprotein B", "g/L", MarkerCategory.LIPID, 0, 1.0, None, None, None, None, 56,
     ["apolipoproteine b", "apo b", "apob"]),
    # --- Glucose metabolism ---
    ("Blood Glucose (fasted)", "mmol/L", MarkerCategory.METABOLIC, 3.9, 5.5, None, None, None, None,
     60, ["glucose", "glucose (naf-bloed)", "nuchtere glucose", "bloedglucose", "fasting glucose"]),
    ("HbA1c", "%", MarkerCategory.METABOLIC, 4.0, 5.7, None, None, None, None, 61,
     ["hba1c", "hba1c (dcct)"]),
    ("HbA1c (IFCC)", "mmol/mol", MarkerCategory.METABOLIC, 20, 39, None, None, None, None, 62,
     ["hba1c (ifcc)", "ifcc"]),
    # --- Renal / muscle ---
    ("Creatinine", "µmol/L", MarkerCategory.KIDNEY, None, None, 64, 104, 49, 90, 70,
     ["creatinine", "kreatinine", "krea"]),
    ("GFR", "mL/min/1.73m²", MarkerCategory.KIDNEY, 90, None, None, None, None, None, 71,
     ["gfr", "egfr", "mdrd", "ckd-epi"]),
    ("CK", "U/L", MarkerCategory.METABOLIC, None, None, 39, 308, 26, 192, 72,
     ["ck", "cpk", "creatinekinase", "creatine kinase"]),
    # --- Electrolytes ---
    ("Magnesium", "mmol/L", MarkerCategory.METABOLIC, 0.70, 1.05, None, None, None, None, 80,
     ["magnesium"]),
    ("Sodium", "mmol/L", MarkerCategory.METABOLIC, 136, 145, None, None, None, None, 81,
     ["natrium", "sodium", "na"]),
    ("Potassium", "mmol/L", MarkerCategory.METABOLIC, 3.6, 5.5, None, None, None, None, 82,
     ["kalium", "potassium", "k"]),
    # --- Vitamins ---
    ("25-hydroxy-vitamin D", "nmol/L", MarkerCategory.OTHER, 75, 250, None, None, None, None, 90,
     ["25-hydroxy-vitamine d", "vitamine d", "vitamin d", "25-oh-vitamine d", "calcidiol"]),
    ("Vitamin B12", "pmol/L", MarkerCategory.OTHER, 145, 569, None, None, None, None, 91,
     ["vitamine b12", "b12", "cobalamine", "vitamin b12"]),
    # --- Inflammation / protein ---
    ("CRP", "mg/L", MarkerCategory.OTHER, 0, 5, None, None, None, None, 100,
     ["crp", "c-reactief proteine", "hs-crp"]),
    ("Albumin", "g/L", MarkerCategory.METABOLIC, 35.0, 52.0, None, None, None, None, 101,
     ["albumine", "albumin"]),
    # --- Thyroid ---
    ("TSH (basal)", "mU/L", MarkerCategory.HORMONE, 0.27, 4.20, None, None, None, None, 110,
     ["tsh", "tsh (basaal)", "thyreotropine"]),
    ("Free T3", "pmol/L", MarkerCategory.HORMONE, 3.08, 6.78, None, None, None, None, 111,
     ["t3 vrij", "vrij t3", "vrije t3", "ft3", "free t3"]),
    ("Free T4", "pmol/L", MarkerCategory.HORMONE, 11.60, 21.90, None, None, None, None, 112,
     ["t4 vrij", "vrij t4", "vrije t4", "ft4", "free t4"]),
    # --- Sex / anabolic hormones ---
    ("LH", "IU/L", MarkerCategory.HORMONE, None, None, 1.7, 8.6, 1.0, 95, 120,
     ["lh", "luteiniserend hormoon"]),
    ("FSH", "IU/L", MarkerCategory.HORMONE, None, None, 1.5, 12.4, 1.0, 150, 121,
     ["fsh", "follikelstimulerend hormoon"]),
    ("Estradiol (E2)", "pmol/L", MarkerCategory.HORMONE, None, None, 41.5, 158.5, 55, 1285, 122,
     ["estradiol", "oestradiol", "e2", "estradiol (17-beta-estradiol)", "17-beta-estradiol"]),
    ("Prolactin", "mU/L", MarkerCategory.HORMONE, None, None, 86, 324, 102, 496, 123,
     ["prolactine", "prolactin", "prl"]),
    ("Testosterone", "nmol/L", MarkerCategory.HORMONE, None, None, 8.64, 29.00, 0.5, 2.4, 124,
     ["testosteron", "testosterone", "testo", "totaal testosteron", "total testosterone"]),
    ("Free Testosterone", "nmol/L", MarkerCategory.HORMONE,
     None, None, 0.225, None, 0.003, 0.03, 125,
     ["testosteron vrij", "vrije testosteron", "testosteron, vrij", "free testosterone"]),
    ("SHBG", "nmol/L", MarkerCategory.HORMONE, None, None, 18.3, 54.1, 32.4, 128, 126,
     ["shbg", "sex hormone binding globulin", "sex.horm.bind.",
      "seksueel hormoonbindend globuline"]),
    ("IGF-1", "nmol/L", MarkerCategory.HORMONE, 11.5, 31.4, None, None, None, None, 127,
     ["igf-1", "igf1", "somatomedine c"]),
    ("Cortisol", "nmol/L", MarkerCategory.HORMONE, 171, 536, None, None, None, None, 128,
     ["cortisol"]),
    ("Progesteron", "nmol/L", MarkerCategory.HORMONE, None, None, 0.6, 4.5, 0.3, 80, 129,
     ["progesteron", "progesterone", "p4"]),
    ("DHEA-S", "µmol/L", MarkerCategory.HORMONE, None, None, 2.2, 15.2, 0.95, 11.7, 130,
     ["dhea-s", "dheas", "dhea sulfaat", "dhea-sulfaat"]),
    ("PSA", "µg/L", MarkerCategory.HORMONE, 0, 4.0, None, None, None, None, 131,
     ["psa", "prostaat specifiek antigeen", "prostate specific antigen"]),
]


def _dec(v):
    return None if v is None else Decimal(str(v))


class Command(BaseCommand):
    help = "Seed compounds, injection sites, and blood markers (idempotent, reference data only)."

    @transaction.atomic
    def handle(self, *args, **options):
        c_new = 0
        for name, cls, unit, route, half_life, ester, active, tmax, bio, src in COMPOUNDS:
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
                    "tmax_hours": Decimal(tmax) if tmax else None,
                    "bioavailability": Decimal(bio) if bio else None,
                    "pk_source": src,
                },
            )
            c_new += created

        for name, region, side, route, x, y in SITES:
            InjectionSite.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name, "region": region, "side": side, "route": route,
                    "x": Decimal(x), "y": Decimal(y),
                },
            )
        # Prune superseded sites (DoseLog.injection_site is SET_NULL, so safe).
        InjectionSite.objects.exclude(slug__in={slugify(s[0]) for s in SITES}).delete()

        m_new = 0
        for (name, unit, cat, lo, hi, lom, him, lof, hif, order, aliases) in MARKERS:
            _, created = BloodMarker.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name, "unit": unit, "category": cat,
                    "ref_low": _dec(lo), "ref_high": _dec(hi),
                    "ref_low_male": _dec(lom), "ref_high_male": _dec(him),
                    "ref_low_female": _dec(lof), "ref_high_female": _dec(hif),
                    "display_order": order, "aliases": aliases,
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
