from allauth.account.models import EmailAddress
from allauth.account.signals import user_signed_up
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, User


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Every user gets exactly one Profile."""
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(user_signed_up)
def mark_email_verified(request, user, **kwargs):
    """Dev convenience: with ACCOUNT_EMAIL_VERIFICATION='none' the email row is
    created unverified, which blocks allauth MFA enrollment ("verify your email
    first"). We treat signups as trusted so TOTP can be set up.

    NOTE: in production, require real email verification before allowing 2FA /
    sensitive data — gate this on settings.DEBUG or remove it (see IMPLEMENTATION_PLAN §10).
    """
    EmailAddress.objects.filter(user=user).update(verified=True)
