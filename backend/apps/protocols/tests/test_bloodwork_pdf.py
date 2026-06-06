"""Parser unit tests for bloodwork PDF import.

The text→rows core is tested on synthetic strings that mimic the real lab layout —
no binary PDF fixture (keeps personal health data out of the repo; the bytes→text
step is thin and covered by the live manual check).
"""
from types import SimpleNamespace

from apps.protocols.bloodwork_pdf import clean_unit, match_marker, parse_report

SAMPLE = """\
EINDRAPPORT van 28.05.26
Afname : 21.05.26 09:20
HEMATOLOGIE
leucocyten            8.7    /nl       4.2 - 9.1
MCV          ↑        98.4   fl        82 - 98
MCHC         ↓        18.5   mmol/l    19.0 - 22.5
HbA1c   HPLC          5.4    %         < 5.7
ijzer   PHOT          20.8   µmol/l    5.9 - 34.5
testosteron  ECLIA ↑  79.90  nmol/l    8.64 - 29.00
testosteron, vrij (volgens   2.840  nmol/l   > 0.125
ISSAM)
SHBG (sex.horm.bind. gl.)  ECLIA ↓  13.5  nmol/l  18.3 - 54.1
cholesterol/HDL       6.3    ratio
natrium  ISE  ↑       >180   mmol/l    136 - 145
   monstermateriaal te oud! Analyse niet mogelijk
Bij een gemiddeld risico :   < 1.0  g/l
CPark Bata,Building 21,Unit 1.23
"""


class TestParseReport:
    def setup_method(self):
        self.rows = {r["raw_name"]: r for r in parse_report(SAMPLE)["rows"]}

    def test_report_date(self):
        assert parse_report(SAMPLE)["measured_on"] == "2026-05-21"

    def test_two_sided_range(self):
        r = self.rows["leucocyten"]
        assert (r["value"], r["unit"], r["ref_low"], r["ref_high"]) == ("8.7", "/nl", "4.2", "9.1")

    def test_flags(self):
        assert self.rows["MCV"]["lab_flag"] == "high"
        assert self.rows["MCHC"]["lab_flag"] == "low"

    def test_one_sided_upper(self):
        assert self.rows["HbA1c"]["ref_low"] is None
        assert self.rows["HbA1c"]["ref_high"] == "5.7"

    def test_method_and_flag_stripped_from_name(self):
        assert "testosteron" in self.rows  # "ECLIA" + "↑" removed from the name
        assert self.rows["testosteron"]["value"] == "79.90"
        assert self.rows["testosteron"]["lab_flag"] == "high"

    def test_free_t_value_on_first_line_one_sided_lower(self):
        ft = next(r for r in self.rows.values() if r["raw_name"].startswith("testosteron, vrij"))
        assert ft["value"] == "2.840"
        assert ft["ref_low"] == "0.125" and ft["ref_high"] is None

    def test_micro_unit(self):
        assert self.rows["ijzer"]["unit"] == "µmol/l"

    def test_skips_noise(self):
        names = list(self.rows)
        assert not any(n.startswith("Bij een") for n in names)  # comparator-prefixed target
        assert "natrium" not in names                            # ">180" censored → no value
        assert not any("CPark" in n for n in names)              # address line


def _marker(name, aliases):
    return SimpleNamespace(name=name, aliases=aliases)


MARKERS = [
    _marker("Leucocytes", ["leucocyten", "wbc"]),
    _marker("Testosterone", ["testosteron", "totaal testosteron"]),
    _marker("Free Testosterone", ["testosteron vrij", "testosteron, vrij"]),
    _marker("HDL", ["hdl-cholesterol", "hdl"]),
    _marker("Total Cholesterol", ["cholesterol", "totaal cholesterol"]),
    _marker("SHBG", ["shbg", "sex.horm.bind."]),
    _marker("Estradiol (E2)", ["estradiol", "estradiol (17-beta-estradiol)"]),
]


class TestMatchMarker:
    def test_exact_alias(self):
        m, conf = match_marker("leucocyten", MARKERS)
        assert m.name == "Leucocytes" and conf == 1.0

    def test_total_testosterone_exact(self):
        assert match_marker("testosteron", MARKERS)[0].name == "Testosterone"

    def test_truncated_free_testosterone_subset(self):
        assert match_marker("testosteron, vrij (volgens", MARKERS)[0].name == "Free Testosterone"

    def test_ratio_not_mismatched(self):
        # "cholesterol/HDL" shares tokens with HDL/Cholesterol but must NOT map to them.
        assert match_marker("cholesterol/HDL", MARKERS)[0] is None

    def test_parenthetical_form(self):
        assert match_marker("estradiol (17-beta-estradiol)", MARKERS)[0].name == "Estradiol (E2)"

    def test_shbg_paren_stripped(self):
        assert match_marker("SHBG (sex.horm.bind. gl.)", MARKERS)[0].name == "SHBG"

    def test_unmatched(self):
        assert match_marker("some unknown analyte", MARKERS) == (None, 0.0)


class TestCleanUnit:
    def test_unifies_micro_and_strips_space(self):
        assert clean_unit(" μmol/l ") == "µmol/l"  # greek mu → micro sign
        assert clean_unit("mmol/l") == "mmol/l"
