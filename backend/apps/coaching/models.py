"""Coach ↔ client relationships.

A `CoachClientLink` connects a coach account (`User.is_coach`) to a client. The
coach invites by email; the client must accept (consent gate) before the link
becomes `active`. Only an active link grants the coach access to the client's
data — see `access.resolve_effective_owner`. Either party can revoke.
"""
from django.conf import settings
from django.db import models


class LinkStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    DECLINED = "declined", "Declined"
    REVOKED = "revoked", "Revoked"


class CoachClientLink(models.Model):
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coaching_links"
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coach_links"
    )
    status = models.CharField(max_length=10, choices=LinkStatus.choices, default=LinkStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["coach", "client"], name="uniq_coach_client"),
        ]
        indexes = [
            models.Index(fields=["client", "status"]),
            models.Index(fields=["coach", "status"]),
        ]

    def __str__(self):
        return f"{self.coach_id}→{self.client_id} ({self.status})"

    @classmethod
    def is_active(cls, coach, client_id) -> bool:
        """True iff `coach` has an accepted, current link to `client_id`."""
        return cls.objects.filter(
            coach=coach, client_id=client_id, status=LinkStatus.ACTIVE
        ).exists()
