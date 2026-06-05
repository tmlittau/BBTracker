import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


def test_healthz_open(api):
    resp = api.get("/api/v1/healthz/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_dashboard_requires_auth(api):
    resp = api.get("/api/v1/dashboard/today/")
    assert resp.status_code in (401, 403)
