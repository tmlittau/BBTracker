"""The single, audited "effective owner" chokepoint for owner-scoped views.

Normally a request acts on `request.user`. A coach may instead target a client
by sending an `X-Acting-Client: <user_id>` header; this resolver returns that
client — but only when the requester is a coach with an *active* link, and:

- **reads** (safe methods) are allowed for any active link;
- **writes** (unsafe methods) are allowed only on views that opt in
  (`prescription_write = True`, i.e. the prescription endpoints) AND only when
  the link grants `can_edit_prescriptions`.

Any header present but not authorised is a hard 403 — we never silently fall
back to the coach's own data. Non-prescription writes always resolve to
`request.user`, so a coach can never write a client's *logged* data.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS

# request.META key for the "X-Acting-Client" header.
ACTING_CLIENT_HEADER = "HTTP_X_ACTING_CLIENT"


def _resolve_client(request, client_id, *, require_write):
    """Return the client `User` if the requester may act on them, else 403."""
    if client_id == getattr(request.user, "id", None):
        return request.user

    from .models import CoachClientLink  # lazy: avoid app-load import cycles

    link = (
        CoachClientLink.active_link(request.user, client_id)
        if getattr(request.user, "is_coach", False)
        else None
    )
    if link is None:
        raise PermissionDenied("You do not have an active coaching link with that client.")
    if require_write and not link.can_edit_prescriptions:
        raise PermissionDenied("You don't have edit access to this client's plan.")

    from apps.accounts.models import User

    return User.objects.get(pk=client_id)


def resolve_effective_owner(request, *, for_write=False):
    """Return the `User` whose data is in scope for this request.

    `for_write=True` (set by prescription views) lets a coach's write resolve to
    the client; otherwise writes resolve to `request.user`.
    """
    raw = request.META.get(ACTING_CLIENT_HEADER)
    if not raw:
        return request.user
    # Writes are only honoured for prescription views that opt in.
    if request.method not in SAFE_METHODS and not for_write:
        return request.user
    try:
        client_id = int(raw)
    except (TypeError, ValueError) as exc:
        raise PermissionDenied("Invalid X-Acting-Client header.") from exc
    require_write = request.method not in SAFE_METHODS
    return _resolve_client(request, client_id, require_write=require_write)


class EffectiveOwnerMixin:
    """Owner-scoped views read their scope from `self.effective_owner` instead of
    `self.request.user`, so a coach acting on a client (safe methods) sees the
    client's data. Writes resolve to `request.user` unless the view sets
    `prescription_write = True` (a prescription endpoint), in which case a coach
    with edit access writes to the client."""

    prescription_write = False

    @property
    def effective_owner(self):
        return resolve_effective_owner(self.request, for_write=self.prescription_write)
