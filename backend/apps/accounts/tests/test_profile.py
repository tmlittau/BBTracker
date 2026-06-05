import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

ME_URL = "/api/v1/auth/me/"


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


def test_patch_updates_own_profile(api, user):
    resp = api.patch(
        ME_URL,
        {"profile": {"sex": "male", "date_of_birth": "1990-05-15",
                     "height_cm": "182.5", "unit_system": "imperial",
                     "timezone": "Europe/Berlin"}},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["profile"]["sex"] == "male"
    assert body["profile"]["unit_system"] == "imperial"

    user.refresh_from_db()
    assert user.profile.sex == "male"
    assert str(user.profile.height_cm) == "182.5"
    assert user.profile.timezone == "Europe/Berlin"


def test_patch_partial_profile(api, user):
    # Only sex provided — other fields keep their defaults.
    resp = api.patch(ME_URL, {"profile": {"sex": "female"}}, format="json")
    assert resp.status_code == 200, resp.content
    user.refresh_from_db()
    assert user.profile.sex == "female"
    assert user.profile.unit_system == "metric"  # unchanged default


def test_patch_can_update_name(api, user):
    resp = api.patch(ME_URL, {"first_name": "Tim", "last_name": "L"}, format="json")
    assert resp.status_code == 200, resp.content
    user.refresh_from_db()
    assert user.first_name == "Tim"


def test_email_is_read_only(api, user):
    resp = api.patch(ME_URL, {"email": "hacked@example.com"}, format="json")
    assert resp.status_code == 200, resp.content
    user.refresh_from_db()
    assert user.email == "a@example.com"  # unchanged


def test_patch_does_not_affect_other_user(api, user, other):
    before = other.profile.sex
    api.patch(ME_URL, {"profile": {"sex": "male"}}, format="json")
    other.refresh_from_db()
    assert other.profile.sex == before  # the other user's profile is untouched
    assert other.profile.sex == "unspecified"


def test_patch_requires_auth():
    resp = APIClient().patch(ME_URL, {"profile": {"sex": "male"}}, format="json")
    assert resp.status_code in (401, 403)


def test_put_not_allowed(api):
    # We expose GET + PATCH only; PUT (full replace) is disabled.
    resp = api.put(ME_URL, {"first_name": "x"}, format="json")
    assert resp.status_code == 405


def test_profile_sex_enables_bloodwork_flagging(api, user):
    """The point of profile editing: sex-specific bloodwork ranges only flag
    once the user's sex is set (Total Testosterone is male/female-ranged)."""
    from datetime import date

    from apps.protocols.models import BloodMarker, BloodResult
    from apps.protocols.services import marker_trend

    tt = BloodMarker.objects.create(
        name="Total Testosterone", slug="total-testosterone", unit="ng/dL",
        category="hormone", ref_low_male=300, ref_high_male=1000,
    )
    BloodResult.objects.create(owner=user, marker=tt, value=250, measured_on=date(2026, 1, 1))

    # Unspecified sex → cannot judge a male/female-only range → in_range.
    assert marker_trend(user, tt, sex=user.profile.sex)[0]["flag"] == "in_range"

    # Set sex via the API, then the same value flags low.
    api.patch(ME_URL, {"profile": {"sex": "male"}}, format="json")
    user.refresh_from_db()
    assert marker_trend(user, tt, sex=user.profile.sex)[0]["flag"] == "low"
