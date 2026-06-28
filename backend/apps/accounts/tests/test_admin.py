"""promote_admin command + the user-deletion cascade the admin relies on."""
import datetime

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import hard_delete_user
from apps.core.models import Phase
from apps.nutrition.models import NutritionTarget
from apps.protocols.models import Compound, DoseLog, Protocol, ProtocolItem

pytestmark = pytest.mark.django_db


def _user_with_protected_compound(email):
    """A user owning a custom compound that their own protocol item + dose log
    PROTECT-reference — the case that makes a plain delete raise ProtectedError."""
    u = User.objects.create_user(email=email, password="x")
    c = Compound.objects.create(
        owner=u, name="Custom Test E", compound_class="anabolic", default_unit="mg"
    )
    p = Protocol.objects.create(owner=u, name="Cycle")
    ProtocolItem.objects.create(
        protocol=p, compound=c, dose_amount="100", dose_unit="mg",
        frequency="weekly", times_of_day=["am"],
    )
    DoseLog.objects.create(
        owner=u, compound=c, taken_at=timezone.now(), amount="100", unit="mg", status="taken"
    )
    return u, c


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


def test_plain_delete_blocked_but_hard_delete_works():
    u, c = _user_with_protected_compound("prot@example.com")
    uid, cid = u.id, c.id

    # A normal cascade delete is blocked by the user's own dose log / protocol item.
    with pytest.raises(ProtectedError):
        u.delete()

    # The ordered teardown removes everything, including the protected compound.
    hard_delete_user(User.objects.get(id=uid))
    assert not User.objects.filter(id=uid).exists()
    assert not Compound.objects.filter(id=cid).exists()
    assert not DoseLog.objects.filter(owner_id=uid).exists()


def test_delete_user_command_removes_protected_user():
    u, _ = _user_with_protected_compound("cmd@example.com")
    uid = u.id
    call_command("delete_user", email="cmd@example.com")
    assert not User.objects.filter(id=uid).exists()


def test_delete_user_command_dry_run_keeps_data():
    _user_with_protected_compound("dry@example.com")
    call_command("delete_user", email="dry@example.com", dry_run=True)
    assert User.objects.filter(email="dry@example.com").exists()
