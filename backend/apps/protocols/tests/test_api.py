from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.nutrition.models import Nutrient
from apps.protocols.models import (
    BloodMarker,
    Compound,
    DoseLog,
    InjectionSite,
    Protocol,
    ProtocolItem,
    Supplement,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(email="a@example.com", password="x")


@pytest.fixture
def other(db):
    return User.objects.create_user(email="b@example.com", password="x")


@pytest.fixture
def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def test_e(db):
    """A global injectable compound with a 7-day half-life (testosterone enanthate-like)."""
    return Compound.objects.create(
        name="Testosterone Enanthate", compound_class="anabolic",
        default_unit="mg", default_route="im",
        half_life_hours="168", ester="enanthate", active_fraction="0.700",
    )


def test_requires_auth():
    assert APIClient().get("/api/v1/protocols/compounds/").status_code in (401, 403)


def test_global_compound_visible(api, test_e):
    names = [c["name"] for c in api.get("/api/v1/protocols/compounds/").json()]
    assert "Testosterone Enanthate" in names


def test_compound_search(api, test_e):
    assert len(api.get("/api/v1/protocols/compounds/?q=enanth").json()) == 1
    assert len(api.get("/api/v1/protocols/compounds/?q=zzz").json()) == 0


def test_compounds_not_paginated(api, user):
    # Whole reference list is returned (no 50-row page cap), as a bare list, so
    # the library + protocol-builder picker can filter/search every compound.
    Compound.objects.bulk_create(
        [Compound(owner=user, name=f"Custom {i:03d}", compound_class="anabolic") for i in range(55)]
    )
    data = api.get("/api/v1/protocols/compounds/").json()
    assert isinstance(data, list)  # bare list, not {count, results}
    assert len([c for c in data if c["name"].startswith("Custom ")]) == 55


def test_custom_compound_owned(api, user):
    resp = api.post(
        "/api/v1/protocols/compounds/",
        {"name": "My Peptide", "compound_class": "peptide", "default_unit": "mcg"},
        format="json",
    )
    assert resp.status_code == 201
    assert Compound.objects.get(name="My Peptide").owner == user


def test_global_compound_is_editable(api, test_e):
    # Single-user app: seeded globals can be edited too.
    resp = api.patch(
        f"/api/v1/protocols/compounds/{test_e.id}/", {"name": "Renamed"}, format="json"
    )
    assert resp.status_code == 200, resp.content
    test_e.refresh_from_db()
    assert test_e.name == "Renamed"


def test_global_compound_delete_blocked_when_referenced(api, test_e):
    spare = Compound.objects.create(name="Spare Global")  # unused global → deletable
    assert api.delete(f"/api/v1/protocols/compounds/{spare.id}/").status_code == 204
    api.post(
        "/api/v1/protocols/dose-logs/",
        {"compound": test_e.id, "taken_at": timezone.now().isoformat(),
         "amount": "100", "unit": "mg", "route": "im"},
        format="json",
    )
    resp = api.delete(f"/api/v1/protocols/compounds/{test_e.id}/")
    assert resp.status_code == 400
    assert "used" in str(resp.json()).lower()
    assert Compound.objects.filter(id=test_e.id).exists()


def test_create_supplement_with_nutrients(api, user, db):
    vit_d = Nutrient.objects.create(
        name="Vitamin D", slug="vitamin_d", category="vitamin", unit="mcg", rda=20
    )
    resp = api.post(
        "/api/v1/protocols/supplements/",
        {
            "name": "Vitamin D3", "serving_label": "1 softgel",
            "supplement_nutrients": [
                {"nutrient": vit_d.id, "amount_per_serving": "125.0000"}
            ],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    supp = Supplement.objects.get(name="Vitamin D3")
    assert supp.owner == user
    assert supp.supplement_nutrients.count() == 1


def test_build_protocol_and_log_dose(api, user, test_e):
    pid = api.post(
        "/api/v1/protocols/protocols/",
        {"name": "TRT", "started_on": "2026-01-01"},
        format="json",
    ).json()["id"]
    item = api.post(
        "/api/v1/protocols/protocol-items/",
        {"protocol": pid, "compound": test_e.id, "dose_amount": "125",
         "dose_unit": "mg", "route": "im", "frequency": "2x_week"},
        format="json",
    )
    assert item.status_code == 201, item.content

    dose = api.post(
        "/api/v1/protocols/dose-logs/",
        {"protocol_item": item.json()["id"], "compound": test_e.id,
         "taken_at": timezone.now().isoformat(), "amount": "125", "unit": "mg", "route": "im"},
        format="json",
    )
    assert dose.status_code == 201, dose.content


def test_delete_own_dose_log(api, test_e):
    dose = api.post(
        "/api/v1/protocols/dose-logs/",
        {"compound": test_e.id, "taken_at": timezone.now().isoformat(),
         "amount": "125", "unit": "mg", "route": "im"},
        format="json",
    )
    assert dose.status_code == 201, dose.content
    did = dose.json()["id"]
    assert api.delete(f"/api/v1/protocols/dose-logs/{did}/").status_code == 204
    assert api.get(f"/api/v1/protocols/dose-logs/{did}/").status_code == 404


def test_cannot_delete_others_dose_log(api, other, test_e):
    other_api = APIClient()
    other_api.force_authenticate(other)
    dose = other_api.post(
        "/api/v1/protocols/dose-logs/",
        {"compound": test_e.id, "taken_at": timezone.now().isoformat(),
         "amount": "100", "unit": "mg", "route": "im"},
        format="json",
    )
    assert dose.status_code == 201, dose.content
    did = dose.json()["id"]
    # The owner-scoped queryset hides another user's dose → 404, and it survives.
    assert api.delete(f"/api/v1/protocols/dose-logs/{did}/").status_code == 404
    assert other_api.get(f"/api/v1/protocols/dose-logs/{did}/").status_code == 200


def test_dose_log_date_range_filter(api, test_e):
    now = timezone.now()
    for days_ago in (0, 15):
        api.post(
            "/api/v1/protocols/dose-logs/",
            {"compound": test_e.id, "taken_at": (now - timedelta(days=days_ago)).isoformat(),
             "amount": "100", "unit": "mg", "route": "im"},
            format="json",
        )
    assert len(api.get("/api/v1/protocols/dose-logs/").json()["results"]) == 2
    frm = (now - timedelta(days=5)).date().isoformat()
    assert len(api.get(f"/api/v1/protocols/dose-logs/?from={frm}").json()["results"]) == 1
    to = (now - timedelta(days=10)).date().isoformat()
    assert len(api.get(f"/api/v1/protocols/dose-logs/?to={to}").json()["results"]) == 1


def test_protocol_item_needs_compound_or_supplement(api, user):
    pid = api.post("/api/v1/protocols/protocols/", {"name": "P"}, format="json").json()["id"]
    resp = api.post(
        "/api/v1/protocols/protocol-items/",
        {"protocol": pid, "dose_amount": "100"},
        format="json",
    )
    assert resp.status_code == 400


def test_cannot_attach_item_to_others_protocol(api, other, test_e):
    theirs = Protocol.objects.create(owner=other, name="Theirs")
    resp = api.post(
        "/api/v1/protocols/protocol-items/",
        {"protocol": theirs.id, "compound": test_e.id, "dose_amount": "100"},
        format="json",
    )
    assert resp.status_code == 403


def test_protocol_activate_exclusive(api):
    p1 = api.post("/api/v1/protocols/protocols/", {"name": "A"}, format="json").json()["id"]
    p2 = api.post("/api/v1/protocols/protocols/", {"name": "B"}, format="json").json()["id"]
    api.post(f"/api/v1/protocols/protocols/{p1}/activate/")
    api.post(f"/api/v1/protocols/protocols/{p2}/activate/")
    assert Protocol.objects.get(id=p1).is_active is False
    assert Protocol.objects.get(id=p2).is_active is True


def test_protocol_release_curve(api, user, test_e):
    # A protocol with a daily Test E item + one logged dose → a per-compound release
    # curve carrying both logged (past) and projected (future) points.
    p = Protocol.objects.create(
        owner=user, name="Cycle", started_on=timezone.now().date() - timedelta(days=7)
    )
    ProtocolItem.objects.create(
        protocol=p, compound=test_e, dose_amount=50, dose_unit="mg", frequency="daily"
    )
    DoseLog.objects.create(
        owner=user, compound=test_e, taken_at=timezone.now() - timedelta(days=1),
        amount=50, unit="mg", route="im",
    )
    resp = api.get(f"/api/v1/protocols/protocols/{p.id}/release/?horizon_days=28")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data["unit"] == "relative"
    assert len(data["compounds"]) == 1
    series = data["compounds"][0]
    assert series["compound_id"] == test_e.id
    assert series["points"]
    assert max(pt["rate"] for pt in series["points"]) > 0
    # Past points are solid (not projected); future points are projected.
    assert any(pt["projected"] for pt in series["points"])
    assert any(not pt["projected"] for pt in series["points"])


def test_protocol_release_excludes_non_mass_units(api, user):
    # An IU-dosed compound (hCG) can't share the mg/day axis → excluded, not plotted.
    hcg = Compound.objects.create(
        name="hCG", compound_class="ancillary", default_unit="iu",
        default_route="subq", half_life_hours="33", active_fraction="1.000",
    )
    p = Protocol.objects.create(owner=user, name="Support")
    ProtocolItem.objects.create(
        protocol=p, compound=hcg, dose_amount=250, dose_unit="iu", frequency="eod"
    )
    data = api.get(f"/api/v1/protocols/protocols/{p.id}/release/").json()
    assert data["compounds"] == []
    assert "hCG" in data["excluded"]


def test_compound_plot(api, test_e):
    # Stateless cycle planner: post a hypothetical item → an overlaid concentration curve.
    resp = api.post(
        "/api/v1/protocols/plot/",
        {"horizon_days": 60, "items": [
            {"compound": test_e.id, "dose_amount": 250, "dose_unit": "mg",
             "frequency": "weekly", "start_day": 0, "duration_days": 56},
        ]},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data["unit"] == "relative"
    assert len(data["compounds"]) == 1
    c = data["compounds"][0]
    assert c["compound_id"] == test_e.id
    assert len(c["points"]) == 61  # day 0..60 inclusive
    assert max(p["level"] for p in c["points"]) > 0


def test_compound_plot_excludes_non_mass(api):
    hcg = Compound.objects.create(
        name="hCG plot", compound_class="ancillary", default_unit="iu",
        default_route="subq", half_life_hours="33", active_fraction="1.000",
    )
    data = api.post(
        "/api/v1/protocols/plot/",
        {"items": [{"compound": hcg.id, "dose_amount": 500, "dose_unit": "iu",
                    "frequency": "daily"}]},
        format="json",
    ).json()
    assert data["compounds"] == []
    assert "hCG plot" in data["excluded"]


def test_injection_sites_carry_route(api):
    InjectionSite.objects.create(
        name="L Glute", slug="l-glute", region="glute", side="left", route="im"
    )
    InjectionSite.objects.create(
        name="L Belly", slug="l-belly", region="lower_belly", side="left", route="subq"
    )
    routes = {s["name"]: s["route"] for s in api.get("/api/v1/protocols/injection-sites/").json()}
    assert routes["L Glute"] == "im"
    assert routes["L Belly"] == "subq"


def test_protocol_item_exposes_compound_route(api, user, test_e):
    # test_e is an injectable (default_route=im); the item's own route is left blank.
    p = Protocol.objects.create(owner=user, name="Cyc")
    ProtocolItem.objects.create(
        protocol=p, compound=test_e, dose_amount=100, dose_unit="mg", frequency="weekly"
    )
    item = api.get(f"/api/v1/protocols/protocols/{p.id}/").json()["items"][0]
    assert item["route"] == ""  # not set on the item
    assert item["compound_route"] == "im"  # so the client falls back to this


def test_parse_pdf(api, monkeypatch):
    # Stub the bytes→text step so no binary PDF fixture is needed; exercise the
    # endpoint + marker matching against a seeded marker.
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.protocols import bloodwork_pdf

    BloodMarker.objects.create(
        name="Testosterone", slug="testosterone", unit="nmol/L",
        category="hormone", aliases=["testosteron"],
    )
    sample = (
        "Afname : 21.05.26 09:20\n"
        "testosteron ECLIA ↑ 79.90 nmol/l 8.64 - 29.00\n"
    )
    monkeypatch.setattr(bloodwork_pdf, "extract_text", lambda _b: sample)
    upload = SimpleUploadedFile("report.pdf", b"%PDF-1.4 dummy", content_type="application/pdf")
    resp = api.post(
        "/api/v1/protocols/blood-results/parse_pdf/", {"file": upload}, format="multipart"
    )
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data["measured_on"] == "2026-05-21"
    row = data["rows"][0]
    assert row["raw_name"] == "testosteron"
    assert row["value"] == "79.90" and row["unit"] == "nmol/l"
    assert row["lab_flag"] == "high"
    assert row["matched"] is True and row["marker"] is not None


def test_bulk_stores_per_result_unit_and_range(api):
    marker = BloodMarker.objects.create(
        name="Testosterone", slug="testosterone", unit="nmol/L", category="hormone"
    )
    resp = api.post(
        "/api/v1/protocols/blood-results/bulk/",
        {
            "measured_on": "2026-05-21",
            "results": [
                {"marker": marker.id, "value": "79.9", "unit": "nmol/l",
                 "ref_low": "8.64", "ref_high": "29.00", "source": "pdf"},
            ],
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    created = resp.json()[0]
    assert created["unit"] == "nmol/l" and created["source"] == "pdf"
    # The matrix flags it via the per-result range (79.9 > 29) and reports the cell unit.
    matrix = api.get("/api/v1/protocols/blood-results/matrix/").json()
    cell = matrix["rows"][0]["cells"][0]
    assert cell["flag"] == "high" and cell["unit"] == "nmol/l"


def test_injection_site_recency_and_suggest(api, user, test_e, db):
    glute_l = InjectionSite.objects.create(
        name="Left glute", slug="left-glute", region="glute", side="left"
    )
    InjectionSite.objects.create(
        name="Right glute", slug="right-glute", region="glute", side="right"
    )
    # Use only the left glute recently.
    DoseLog.objects.create(
        owner=user, compound=test_e, taken_at=timezone.now(),
        amount=125, unit="mg", route="im", injection_site=glute_l,
    )
    recency = api.get("/api/v1/protocols/injection-sites/recency/").json()
    by_name = {r["name"]: r for r in recency}
    assert by_name["Left glute"]["status"] == "fresh"
    assert by_name["Right glute"]["status"] == "rested"  # never used

    # Suggestion should avoid the freshly-used left glute.
    suggestion = api.get("/api/v1/protocols/injection-sites/suggest/").json()
    assert suggestion["name"] != "Left glute"


def test_suggest_site_with_no_doses(api, db):
    """A brand-new user (no doses → all sites never-used) must not 500.

    Regression: the suggestion sort used a tuple key that could fall through to
    comparing row dicts when every site tied as never-used.
    """
    InjectionSite.objects.create(name="Left glute", slug="left-glute", region="glute", side="left")
    InjectionSite.objects.create(name="Right quad", slug="right-quad", region="quad", side="right")
    resp = api.get("/api/v1/protocols/injection-sites/suggest/")
    assert resp.status_code == 200
    assert resp.json()["name"] in {"Left glute", "Right quad"}


def test_adherence(api, user, test_e):
    pid = api.post("/api/v1/protocols/protocols/", {"name": "TRT"}, format="json").json()["id"]
    item = api.post(
        "/api/v1/protocols/protocol-items/",
        {"protocol": pid, "compound": test_e.id, "dose_amount": "125", "frequency": "2x_week"},
        format="json",
    ).json()
    # Expect 2/week × 4 weeks = 8; log 4 → 50%.
    now = timezone.now()
    for i in range(4):
        DoseLog.objects.create(
            owner=user, protocol_item_id=item["id"], compound=test_e,
            taken_at=now - timedelta(days=i * 3), amount=125, unit="mg",
        )
    rows = api.get(f"/api/v1/protocols/protocols/{pid}/adherence/?window_days=28").json()
    assert rows[0]["expected"] == 8.0
    assert rows[0]["actual"] == 4
    assert rows[0]["adherence"] == 50


def test_bloodwork_trend_with_flags(api, user, db):
    marker = BloodMarker.objects.create(
        name="Total Testosterone", slug="total-t", unit="ng/dL",
        category="hormone", ref_low=300, ref_high=1000,
    )
    api.post(
        "/api/v1/protocols/blood-results/",
        {"marker": marker.id, "value": "250", "measured_on": "2026-01-01"},
        format="json",
    )
    api.post(
        "/api/v1/protocols/blood-results/",
        {"marker": marker.id, "value": "650", "measured_on": "2026-03-01"},
        format="json",
    )
    trend = api.get(f"/api/v1/protocols/blood-results/trend/?marker={marker.id}").json()
    assert len(trend) == 2
    assert trend[0]["flag"] == "low"        # 250 < 300
    assert trend[1]["flag"] == "in_range"   # 650 in [300,1000]


def test_bp_log(api, user):
    resp = api.post(
        "/api/v1/protocols/bp-logs/",
        {"systolic": 122, "diastolic": 78, "pulse": 60,
         "measured_at": timezone.now().isoformat()},
        format="json",
    )
    assert resp.status_code == 201


def test_compound_owner_isolation(api, other, test_e):
    Compound.objects.create(owner=None, name="Global one")  # visible to all
    Compound.objects.create(owner=other, name="Their custom")  # not visible
    listed = api.get("/api/v1/protocols/compounds/").json()
    names = {c["name"] for c in listed}
    assert "Global one" in names
    assert "Their custom" not in names


def test_supplement_feeds_nutrition_summary(api, user, db):
    """A logged supplement dose contributes its micros to the nutrition summary."""
    vit_c = Nutrient.objects.create(
        name="Vitamin C", slug="vitamin_c", category="vitamin", unit="mg", rda=90
    )
    supp = Supplement.objects.create(name="Vitamin C 500", owner=user)
    supp.supplement_nutrients.create(nutrient=vit_c, amount_per_serving=500)

    DoseLog.objects.create(
        owner=user, supplement=supp,
        taken_at=timezone.make_aware(timezone.datetime(2026, 5, 30, 8, 0)),
        amount=1, unit="capsule",
    )
    resp = api.get("/api/v1/nutrition/summary/?date=2026-05-30")
    assert resp.status_code == 200
    by_slug = {n["slug"]: n for n in resp.json()["nutrients"]}
    # 500 mg from the supplement should show up against Vitamin C.
    assert float(by_slug["vitamin_c"]["amount"]) == 500.0


def test_supplement_mass_dose_counts_as_one_serving(api, user, db):
    """Regression: a supplement logged in a mass unit (e.g. 1000 mg fish oil) must
    NOT multiply its per-serving macros by the dose amount."""
    fat = Nutrient.objects.create(name="Fat", slug="fat", category="macro", unit="g")
    energy = Nutrient.objects.create(
        name="Energy", slug="energy", category="energy", unit="kcal", is_energy=True
    )
    omega = Supplement.objects.create(name="Omega 3", owner=user)
    omega.supplement_nutrients.create(nutrient=fat, amount_per_serving=1)
    omega.supplement_nutrients.create(nutrient=energy, amount_per_serving=10)
    DoseLog.objects.create(
        owner=user, supplement=omega,
        taken_at=timezone.make_aware(timezone.datetime(2026, 5, 30, 8, 0)),
        amount=1000, unit="mg",
    )
    summary = api.get("/api/v1/nutrition/summary/?date=2026-05-30").json()
    by_slug = {n["slug"]: n for n in summary["nutrients"]}
    assert float(by_slug["fat"]["amount"]) == 1.0  # one serving, not 1000
    assert float(by_slug["energy"]["amount"]) == 10.0


def test_supplement_capsule_count_scales_servings(api, user, db):
    """Count-based units still scale: 2 capsules = 2× the per-serving nutrients."""
    fat = Nutrient.objects.create(name="Fat", slug="fat", category="macro", unit="g")
    omega = Supplement.objects.create(name="Omega 3", owner=user)
    omega.supplement_nutrients.create(nutrient=fat, amount_per_serving=1)
    DoseLog.objects.create(
        owner=user, supplement=omega,
        taken_at=timezone.make_aware(timezone.datetime(2026, 5, 30, 8, 0)),
        amount=2, unit="capsule",
    )
    summary = api.get("/api/v1/nutrition/summary/?date=2026-05-30").json()
    by_slug = {n["slug"]: n for n in summary["nutrients"]}
    assert float(by_slug["fat"]["amount"]) == 2.0


def test_skipped_supplement_not_counted(api, user, db):
    """A skipped supplement dose must not feed the nutrition totals."""
    vit_c = Nutrient.objects.create(
        name="Vitamin C", slug="vitamin_c", category="vitamin", unit="mg"
    )
    supp = Supplement.objects.create(name="C", owner=user)
    supp.supplement_nutrients.create(nutrient=vit_c, amount_per_serving=500)
    DoseLog.objects.create(
        owner=user, supplement=supp,
        taken_at=timezone.make_aware(timezone.datetime(2026, 5, 30, 8, 0)),
        amount=1, unit="capsule", status="skipped",
    )
    summary = api.get("/api/v1/nutrition/summary/?date=2026-05-30").json()
    by_slug = {n["slug"]: n for n in summary["nutrients"]}
    assert float(by_slug["vitamin_c"]["amount"]) == 0.0


def test_phase_dose_matrix(api, user, test_e, db):
    """Phase matrix: injectable anabolic = weekly mode; taken/skipped counted per week."""
    from datetime import date

    from apps.core.models import Phase

    start = date(2026, 5, 1)
    phase = Phase.objects.create(
        owner=user, name="Cut", start_date=start, end_date=start + timedelta(days=20)
    )
    p = Protocol.objects.create(owner=user, name="Cycle", started_on=start)
    ProtocolItem.objects.create(
        protocol=p, compound=test_e, dose_amount=125, dose_unit="mg",
        route="im", frequency="2x_week",
    )
    for day, status in ((2, "taken"), (3, "skipped")):  # both in week 0
        DoseLog.objects.create(
            owner=user, compound=test_e,
            taken_at=timezone.make_aware(timezone.datetime(2026, 5, day, 9, 0)),
            amount=125, unit="mg", route="im", status=status,
        )
    data = api.get(
        f"/api/v1/protocols/protocols/{p.id}/phase_matrix/?phase={phase.id}"
    ).json()
    assert data["phase"]["name"] == "Cut"
    assert len(data["weeks"]) == 3  # 21 days → 3 weekly columns
    row = data["rows"][0]
    assert row["mode"] == "weekly"  # injectable anabolic aggregates to a weekly dose
    assert row["cells"][0]["taken_count"] == 1
    assert row["cells"][0]["skipped_count"] == 1
    assert float(row["cells"][0]["taken_amount"]) == 125.0


def test_phase_matrix_is_not_n_plus_one(django_assert_max_num_queries, user, test_e, db):
    """Dose-table matrix must not issue a query per item (batched dose fetch)."""
    from datetime import date

    from apps.core.models import Phase
    from apps.protocols.services import phase_dose_matrix

    start = date(2026, 5, 1)
    phase = Phase.objects.create(
        owner=user, name="Cut", start_date=start, end_date=start + timedelta(days=13)
    )
    p = Protocol.objects.create(owner=user, name="Cycle", started_on=start)
    comps = [test_e] + [
        Compound.objects.create(
            name=f"PM{i}", compound_class="anabolic", default_unit="mg",
            default_route="im", half_life_hours="120", active_fraction="0.800",
        )
        for i in range(4)
    ]
    for c in comps:
        ProtocolItem.objects.create(
            protocol=p, compound=c, dose_amount=100, dose_unit="mg",
            route="im", frequency="2x_week",
        )
    # 5 items: the old per-item query would be ~6; batched is constant.
    with django_assert_max_num_queries(4):
        data = phase_dose_matrix(user, phase, p)
    assert len(data["rows"]) == 5


def test_release_curves_is_not_n_plus_one(django_assert_max_num_queries, user, test_e, db):
    """Release curve must not issue a query per compound (batched dose fetch)."""
    from apps.protocols.services import protocol_release_curves

    p = Protocol.objects.create(
        owner=user, name="Cycle", started_on=timezone.now().date() - timedelta(days=10)
    )
    comps = [test_e] + [
        Compound.objects.create(
            name=f"RC{i}", compound_class="anabolic", default_unit="mg",
            default_route="im", half_life_hours="168", active_fraction="0.700",
        )
        for i in range(3)
    ]
    for c in comps:
        ProtocolItem.objects.create(
            protocol=p, compound=c, dose_amount=100, dose_unit="mg",
            route="im", frequency="weekly",
        )
        DoseLog.objects.create(
            owner=user, compound=c, taken_at=timezone.now() - timedelta(days=3),
            amount=100, unit="mg", route="im",
        )
    # 4 compounds: old code did one query per compound; batched is constant.
    with django_assert_max_num_queries(5):
        data = protocol_release_curves(user, p, horizon_days=14)
    assert len(data["compounds"]) == 4
