import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

SIGNUP_URL = "/_allauth/browser/v1/auth/signup"
ME_URL = "/api/v1/auth/me/"


@pytest.fixture
def api():
    return APIClient()


def test_me_requires_auth(api):
    resp = api.get(ME_URL)
    assert resp.status_code in (401, 403)


def test_signup_then_me(api):
    resp = api.post(
        SIGNUP_URL,
        {"email": "lifter@example.com", "password": "Sup3rStrongPass!"},
        format="json",
    )
    assert resp.status_code in (200, 201), resp.content

    me = api.get(ME_URL)
    assert me.status_code == 200, me.content
    body = me.json()
    assert body["email"] == "lifter@example.com"
    # Profile is auto-created with sensible defaults.
    assert body["profile"]["unit_system"] == "metric"


def test_profile_created_on_signup(api):
    from apps.accounts.models import User

    resp = api.post(
        SIGNUP_URL,
        {"email": "newlifter@example.com", "password": "Sup3rStrongPass!"},
        format="json",
    )
    assert resp.status_code in (200, 201), resp.content
    user = User.objects.get(email="newlifter@example.com")
    assert hasattr(user, "profile")
    assert user.profile.timezone == "UTC"


def test_signup_marks_email_verified(api):
    """The user_signed_up signal verifies the email so MFA can be enrolled."""
    from allauth.account.models import EmailAddress

    api.post(
        SIGNUP_URL,
        {"email": "verified@example.com", "password": "Sup3rStrongPass!"},
        format="json",
    )
    assert EmailAddress.objects.filter(email="verified@example.com", verified=True).exists()


def test_totp_enrollment_available_after_signup(api):
    """GET on the TOTP authenticator returns an enrollment secret (no email-verify block)."""
    api.post(
        SIGNUP_URL,
        {"email": "totp@example.com", "password": "Sup3rStrongPass!"},
        format="json",
    )
    resp = api.get("/_allauth/browser/v1/account/authenticators/totp")
    # 200/404/409 all carry the enrollment secret in allauth's body depending on version;
    # the key assertion is that it is NOT the 409 "verify your email first" error.
    body = resp.json()
    meta = body.get("meta") or body.get("data", {}).get("meta", {})
    assert meta.get("secret"), f"expected enrollment secret, got {resp.status_code} {body}"
