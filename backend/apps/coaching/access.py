"""The single, audited "effective owner" chokepoint for owner-scoped views.

Normally a request acts on `request.user`. A coach may instead target a client
by sending an `X-Acting-Client: <user_id>` header; this resolver returns that
client — but ONLY for safe (read) methods, and ONLY when the requester is a
coach with an *active* link to that client. Anything else is a hard 403; we
never silently fall back to the coach's own data when a header is present.

Writes always resolve to `request.user` (the resolver ignores the header on
unsafe methods), so the read-only guarantee holds even if a write endpoint is
ever missed during wiring.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS

# request.META key for the "X-Acting-Client" header.
ACTING_CLIENT_HEADER = "HTTP_X_ACTING_CLIENT"


def resolve_effective_owner(request):
    """Return the `User` whose data is in scope for this request."""
    raw = request.META.get(ACTING_CLIENT_HEADER)
    if not raw:
        return request.user
    # The header is only honoured on reads — a coach can never write client data.
    if request.method not in SAFE_METHODS:
        return request.user
    try:
        client_id = int(raw)
    except (TypeError, ValueError) as exc:
        raise PermissionDenied("Invalid X-Acting-Client header.") from exc
    if client_id == getattr(request.user, "id", None):
        return request.user

    from .models import CoachClientLink  # lazy: avoid app-load import cycles

    if not getattr(request.user, "is_coach", False) or not CoachClientLink.is_active(
        request.user, client_id
    ):
        raise PermissionDenied("You do not have an active coaching link with that client.")

    from apps.accounts.models import User

    return User.objects.get(pk=client_id)


class EffectiveOwnerMixin:
    """Owner-scoped views read their scope from `self.effective_owner` instead of
    `self.request.user`, so a coach acting on a client (safe methods) sees the
    client's data. Writes continue to use `request.user`."""

    @property
    def effective_owner(self):
        return resolve_effective_owner(self.request)
