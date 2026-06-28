"""Grant (or revoke) Django-admin access for an existing account, by email.

Use this to give your own account access to /admin/ — accounts created through the
app's signup are normal users (is_staff=False), so they can't reach the admin until
promoted:

    python manage.py promote_admin --email you@example.com
    python manage.py promote_admin --email you@example.com --revoke
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Grant or revoke Django admin access (is_staff + is_superuser) for a user by email."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Email of the user to promote.")
        parser.add_argument(
            "--revoke", action="store_true", help="Remove admin access instead of granting it."
        )

    def handle(self, *args, **opts):
        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=opts["email"])
        except user_model.DoesNotExist as exc:
            raise CommandError(f"No user with email {opts['email']!r}.") from exc
        grant = not opts["revoke"]
        user.is_staff = grant
        user.is_superuser = grant
        user.save(update_fields=["is_staff", "is_superuser"])
        verb = "now has" if grant else "no longer has"
        self.stdout.write(self.style.SUCCESS(f"{user.email} {verb} Django admin access."))
