"""promote_admin command + the user-deletion cascade the admin relies on."""
import datetime

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.core.models import Phase
from apps.nutrition.models import NutritionTarget
from apps.protocols.models import Protocol

pytestmark = pytest.mark.django_db


def test_promote_admin_grants_then_revokes():
    u = User.objects.create_user(email="boss@example.com", password="x")
    assert not u.is_staff and not u.is_superuser

    call_command("promote_admin", email="boss@example.com")
    u.refresh_from_db()
    assert u.is_staff and u.is_superuser

    call_command("promote_admin", email="BOSS@example.com", revoke=True)  # case-insensitive
    u.refresh_from_db()
    assert not u.is_staff and not u.is_superuser


def test_promote_admin_unknown_email_errors():
    with pytest.raises(CommandError):
        call_command("promote_admin", email="nobody@example.com")


def test_deleting_user_cascades_their_data():
    """Deleting a user removes all their owned rows across apps (what the admin's
    'delete user' does), so there's no orphaned data left behind."""
    u = User.objects.create_user(email="gone@example.com", password="x")
    uid = u.id
    Protocol.objects.create(owner=u, name="Cycle")
    NutritionTarget.objects.create(owner=u, name="Cut")
    Phase.objects.create(
        owner=u, name="Prep", phase_type="bulk", start_date=datetime.date(2026, 1, 1)
    )

    u.delete()

    assert not Protocol.objects.filter(owner_id=uid).exists()
    assert not NutritionTarget.objects.filter(owner_id=uid).exists()
    assert not Phase.objects.filter(owner_id=uid).exists()
