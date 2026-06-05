from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserSerializer


@extend_schema(tags=["auth"])
class MeView(RetrieveUpdateAPIView):
    """Return (GET) or update (PATCH) the current user and their nested profile.

    Always scoped to `request.user`, so a user can only read/edit their own
    account; email is read-only. PUT is disabled — clients send partial PATCHes.
    """

    serializer_class = UserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFView(APIView):
    """GET once on app load to ensure the csrftoken cookie is set.

    The SvelteKit client then echoes it back as the X-CSRFToken header on
    unsafe requests (Django / allauth session CSRF protection).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["auth"],
        responses=inline_serializer(name="Csrf", fields={"detail": serializers.CharField()}),
    )
    def get(self, request):
        return Response({"detail": "CSRF cookie set"})
