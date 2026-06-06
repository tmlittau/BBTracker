"""Iteration-2 protocols: day-of-week + time-of-day scheduling adherence,
and the bloodwork bulk-create + tabular matrix."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.protocols.models import BloodMarker, BloodResult, Compound

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(email="p2@example.com", password="x")


@pytest.fixture
def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def test_e(db):
    return Compound.objects.create(
        name="Testosterone Enanthate", compound_class="anabolic",
        default_unit="mg", default_route="im", half_life_hours="168",
        ester="enanthate", active_fraction="0.700",
    )


def test_specific_days_times_adherence(api, user, test_e):
    pid = api.post("/api/v1/protocols/protocols/", {"name": "Cycle"}, format="json").json()["id"]
    item = api.post(
        "/api/v1/protocols/protocol-items/",
        {"protocol": pid, "compound": test_e.id, "dose_amount": "50",
         "frequency": "specific_days", "days_of_week": [0, 2, 4], "times_of_day": ["am", "pm"]},
        format="json",
    ).json()
    assert item["days_of_week"] == [0, 2, 4]
    assert item["times_of_day"] == ["am", "pm"]
    # Any 7-day window has exactly one Mon/Wed/Fri → 3 days × 2 times = 6 expected.
    rows = api.get(f"/api/v1/protocols/protocols/{pid}/adherence/?window_days=7").json()
    assert rows[0]["expected"] == 6.0


def test_every_3_days_adherence(api, user, test_e):
    pid = api.post("/api/v1/protocols/protocols/", {"name": "Peptide"}, format="json").json()["id"]
    api.post(
        "/api/v1/protocols/protocol-items/",
        {"protocol": pid, "compound": test_e.id, "dose_amount": "1", "frequency": "every_3_days"},
        format="json",
    )
    rows = api.get(f"/api/v1/protocols/protocols/{pid}/adherence/?window_days=30").json()
    assert rows[0]["expected"] == 10.0  # 30 / 3 × 1


def test_bloodwork_bulk_skips_blank_and_invalid(api, user):
    a = BloodMarker.objects.create(name="ALT", slug="alt", unit="U/L", category="liver",
                                   ref_low=7, ref_high=56)
    b = BloodMarker.objects.create(name="AST", slug="ast", unit="U/L", category="liver",
                                   ref_low=10, ref_high=40)
    resp = api.post(
        "/api/v1/protocols/blood-results/bulk/",
        {"measured_on": "2026-02-01", "results": [
            {"marker": a.id, "value": "30"},
            {"marker": b.id, "value": ""},        # blank → skipped
            {"marker": 99999, "value": "5"},      # unknown marker → skipped
        ]},
        format="json",
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 1
    assert BloodResult.objects.filter(owner=user).count() == 1


def test_bloodwork_matrix(api, user):
    tt = BloodMarker.objects.create(name="Total T", slug="tt", unit="ng/dL", category="hormone",
                                    ref_low=300, ref_high=1000, display_order=1)
    hct = BloodMarker.objects.create(name="Hematocrit", slug="hct", unit="%", category="blood",
                                     ref_low=40, ref_high=50, display_order=2)
    BloodMarker.objects.create(name="Never", slug="never", unit="x", category="other")  # omitted

    # Two draws; Total T both dates, Hematocrit only the 2nd.
    api.post("/api/v1/protocols/blood-results/bulk/",
             {"measured_on": "2026-01-01", "results": [{"marker": tt.id, "value": "250"}]},
             format="json")
    api.post("/api/v1/protocols/blood-results/bulk/",
             {"measured_on": "2026-03-01",
              "results": [{"marker": tt.id, "value": "500"}, {"marker": hct.id, "value": "52"}]},
             format="json")

    m = api.get("/api/v1/protocols/blood-results/matrix/").json()
    assert m["dates"] == ["2026-01-01", "2026-03-01"]
    rows = {r["marker"]: r for r in m["rows"]}
    assert set(rows) == {"Total T", "Hematocrit"}  # "Never" omitted

    tt_cells = rows["Total T"]["cells"]
    assert tt_cells[0]["value"] == "250.000" and tt_cells[0]["flag"] == "low"
    assert tt_cells[1]["flag"] == "in_range"
    assert tt_cells[1]["pct_change"] == 100.0     # 250 → 500

    hct_cells = rows["Hematocrit"]["cells"]
    assert hct_cells[0] is None                    # not measured on the 1st date
    assert hct_cells[1]["flag"] == "high"          # 52 > 50
