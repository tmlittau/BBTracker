from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.analysis import services
from apps.analysis.models import BodyMeasurement

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    u = User.objects.create_user(email="a@example.com", password="x")
    u.profile.sex = "male"
    u.profile.height_cm = 180
    u.profile.date_of_birth = date(1990, 1, 1)
    u.profile.save()
    return u


@pytest.fixture
def other(db):
    return User.objects.create_user(email="b@example.com", password="x")


@pytest.fixture
def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


# --- Pure formula checks ------------------------------------------------------


def test_navy_and_rfm_body_fat():
    # Known-ish values: 180 cm, neck 38, waist 85 → ~15% (Navy, male).
    bf = services.navy_body_fat("male", 180, 38, 85)
    assert 20 < bf < 25  # ~22.6% for waist 85 / neck 38 / height 180
    r = services.rfm("male", 180, 85)
    assert 15 < r < 25  # RFM: 64 - 20*(180/85) = ~21.6


def test_ffmi_and_lean_mass():
    fat, lean = services.lean_fat_mass(90, 15)
    assert fat == 13.5 and lean == 76.5
    raw, norm = services.ffmi(lean, 180)
    assert 22 < raw < 25  # 76.5 / 1.8^2 = 23.6


def test_adaptive_tdee_recovers_expenditure():
    # Construct a clean signal: eat 2500/day, lose 0.5 kg/week → expenditure ~3050.
    base = date(2026, 1, 1)
    weight = {base + timedelta(days=i): 90.0 - (0.5 / 7) * i for i in range(28)}
    intake = {base + timedelta(days=i): 2500 for i in range(28)}
    res = services.adaptive_tdee(intake, weight)
    assert res is not None
    assert abs(res["tdee"] - (2500 + (0.5 / 7) * 7700)) < 50
    assert res["weight_slope_kg_wk"] < 0
    assert res["confidence"] == "high"


def test_adaptive_tdee_needs_enough_data():
    base = date(2026, 1, 1)
    assert services.adaptive_tdee({}, {base: 90.0, base + timedelta(days=1): 89.9}) is None


# --- API ----------------------------------------------------------------------


def test_measurement_crud_and_unit(api, user):
    resp = api.post(
        "/api/v1/analysis/measurements/",
        {"date": "2026-06-01", "type": "waist", "value": "85"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["unit"] == "cm"
    bf = api.post(
        "/api/v1/analysis/measurements/",
        {"date": "2026-06-01", "type": "body_fat", "value": "14.5", "method": "dexa"},
        format="json",
    )
    assert bf.json()["unit"] == "%"
    assert BodyMeasurement.objects.filter(owner=user).count() == 2


def test_measurement_owner_isolation(api, other):
    theirs = BodyMeasurement.objects.create(owner=other, date=date.today(), type="waist", value=80)
    assert api.get(f"/api/v1/analysis/measurements/{theirs.id}/").status_code == 404


def test_body_analysis_endpoint(api, user):
    BodyMeasurement.objects.create(owner=user, date=date.today(), type="waist", value=85)
    BodyMeasurement.objects.create(owner=user, date=date.today(), type="neck", value=38)
    from apps.diary.models import CheckIn

    CheckIn.objects.create(owner=user, date=date.today(), bodyweight=90, systolic=118, diastolic=76)

    data = api.get("/api/v1/analysis/body/").json()
    assert data["sex"] == "male"
    assert data["composition"]["body_fat_source"] == "navy"  # waist+neck present, no DEXA
    assert data["composition"]["body_fat_pct"] is not None
    assert data["distribution"]["waist_to_height"] == round(85 / 180, 3)
    assert data["energy"]["bmr_mifflin"] is not None
    # An assessment for waist-to-height should be present and "good" (0.47).
    whtr = next(a for a in data["assessments"] if a["key"] == "whtr")
    assert whtr["status"] == "good"
    assert any(a["key"] == "blood_pressure" and a["status"] == "good" for a in data["assessments"])


def test_free_testosterone_and_egfr():
    ft = services.free_testosterone(20, 30, 43)  # TT 20 nmol/L, SHBG 30, albumin 43 g/L
    assert ft is not None
    assert 300 < ft["free_pmol_l"] < 600  # ~2% of total → normal free T
    assert ft["free_pct"] > 1
    gfr = services.egfr_ckdepi(80, 35, "male")  # creatinine 80 µmol/L, 35yo male
    assert 90 < gfr < 130


def test_composition_series_and_insights(user):
    from apps.diary.models import CheckIn

    base = date(2026, 1, 1)
    CheckIn.objects.create(owner=user, date=base, bodyweight=90)
    CheckIn.objects.create(owner=user, date=base + timedelta(days=60), bodyweight=87)
    BodyMeasurement.objects.create(owner=user, date=base, type="body_fat", value=20, method="dexa")
    BodyMeasurement.objects.create(
        owner=user, date=base + timedelta(days=60), type="body_fat", value=15, method="dexa"
    )
    series = services.composition_series(
        user, base - timedelta(days=1), base + timedelta(days=61), "male", 180
    )
    assert len(series) == 2
    assert series[0]["fat_mass_kg"] == 18.0
    assert series[-1]["fat_mass_kg"] == 13.05  # 87 * 0.15
    ins = services._insights(series, {})
    assert any(i["key"] == "cut_quality" for i in ins)  # fat down, lean held


def test_phase2_keys_in_endpoint(api):
    data = api.get("/api/v1/analysis/body/").json()
    assert isinstance(data["composition_trend"], list)
    assert isinstance(data["insights"], list)
    assert "derived" in data["bloodwork"] and "trends" in data["bloodwork"]
