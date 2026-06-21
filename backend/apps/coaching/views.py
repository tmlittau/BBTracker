"""Coaching API: a coach's client list + per-client read overview, plus the
invite / accept / revoke lifecycle. All data access to a client's records goes
through an active CoachClientLink check (here and in `access.resolve_effective_owner`).
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.analysis.services import body_analysis
from apps.core.models import Phase
from apps.core.services import dashboard_today, weekly_checkin
from apps.diary.models import CheckIn

from .models import CoachClientLink, LinkStatus
from .serializers import (
    ClientBriefSerializer,
    InviteCreateSerializer,
    InviteRespondSerializer,
    LinkPermissionSerializer,
    LinkSerializer,
)


def _name(user):
    return (user.get_full_name() or "").strip() or user.email


def _require_active_link(coach, client_id):
    """403 unless `coach` is a coach with an active link to `client_id`."""
    if not getattr(coach, "is_coach", False) or not CoachClientLink.is_active(coach, client_id):
        raise PermissionDenied("You do not have an active coaching link with that client.")


def _client_brief(link):
    client = link.client
    last = CheckIn.objects.filter(owner=client).order_by("-date").first()
    today = timezone.localdate()
    phase = (
        Phase.objects.filter(owner=client, start_date__lte=today)
        .filter(Q(end_date__gte=today) | Q(end_date__isnull=True))
        .order_by("-start_date")
        .first()
    )
    bw = last.bodyweight if (last and last.bodyweight is not None) else None
    return {
        "link_id": link.id,
        "client_id": client.id,
        "email": client.email,
        "name": _name(client),
        "status": link.status,
        "can_edit_prescriptions": link.can_edit_prescriptions,
        "phase": phase.name if phase else None,
        "last_check_in": last.date if last else None,
        "bodyweight": float(bw) if bw is not None else None,
    }


class CoachClientListView(APIView):
    """A coach's active clients, each with a brief snapshot."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["coaching"], responses=ClientBriefSerializer(many=True))
    def get(self, request):
        if not request.user.is_coach:
            raise PermissionDenied("Your account is not enabled for coaching.")
        links = (
            CoachClientLink.objects.filter(coach=request.user, status=LinkStatus.ACTIVE)
            .select_related("client")
            .order_by("client__email")
        )
        data = ClientBriefSerializer([_client_brief(link) for link in links], many=True).data
        return Response(data)


class ClientOverviewView(APIView):
    """At-a-glance read snapshot of one client (coach only, active link required)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["coaching"], responses=OpenApiTypes.OBJECT)
    def get(self, request, client_id):
        _require_active_link(request.user, client_id)
        client = get_object_or_404(User, pk=client_id)
        today = timezone.localdate()
        return Response(
            {
                "client": {"id": client.id, "email": client.email, "name": _name(client)},
                "dashboard": dashboard_today(client, today),
                "weekly_check_in": weekly_checkin(client, today),
                "body": body_analysis(client, today),
            }
        )


class InviteListCreateView(APIView):
    """GET: invites this user has sent (as coach) + received (as client).
    POST: a coach invites a client by email."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["coaching"], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        sent = (
            CoachClientLink.objects.filter(coach=request.user)
            .select_related("coach", "client")
            .order_by("-created_at")
        )
        received = (
            CoachClientLink.objects.filter(client=request.user, status=LinkStatus.PENDING)
            .select_related("coach", "client")
            .order_by("-created_at")
        )
        return Response(
            {
                "sent": LinkSerializer(sent, many=True).data,
                "received": LinkSerializer(received, many=True).data,
            }
        )

    @extend_schema(
        tags=["coaching"], request=InviteCreateSerializer, responses=LinkSerializer
    )
    def post(self, request):
        if not request.user.is_coach:
            raise PermissionDenied("Your account is not enabled for coaching.")
        ser = InviteCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]
        client = User.objects.filter(email__iexact=email).first()
        if client is None:
            raise ValidationError({"email": "No BBTracker account with that email."})
        if client == request.user:
            raise ValidationError({"email": "You can't add yourself as a client."})
        link, created = CoachClientLink.objects.get_or_create(
            coach=request.user, client=client, defaults={"status": LinkStatus.PENDING}
        )
        if not created:
            if link.status == LinkStatus.ACTIVE:
                raise ValidationError({"email": "Already an active client."})
            if link.status == LinkStatus.PENDING:
                raise ValidationError({"email": "An invite is already pending."})
            # Re-invite after a decline/revoke.
            link.status = LinkStatus.PENDING
            link.responded_at = None
            link.save(update_fields=["status", "responded_at"])
        return Response(LinkSerializer(link).data, status=status.HTTP_201_CREATED)


class InviteRespondView(APIView):
    """A client accepts or declines a pending invite addressed to them."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["coaching"], request=InviteRespondSerializer, responses=LinkSerializer
    )
    def post(self, request, pk):
        link = get_object_or_404(CoachClientLink, pk=pk, client=request.user)
        if link.status != LinkStatus.PENDING:
            raise ValidationError("This invite is no longer pending.")
        ser = InviteRespondSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        link.status = LinkStatus.ACTIVE if ser.validated_data["accept"] else LinkStatus.DECLINED
        link.responded_at = timezone.now()
        link.save(update_fields=["status", "responded_at"])
        return Response(LinkSerializer(link).data)


class LinkRevokeView(APIView):
    """Either party ends an active or pending link."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["coaching"], request=None, responses=LinkSerializer)
    def post(self, request, pk):
        link = get_object_or_404(
            CoachClientLink, Q(coach=request.user) | Q(client=request.user), pk=pk
        )
        link.status = LinkStatus.REVOKED
        link.responded_at = timezone.now()
        link.save(update_fields=["status", "responded_at"])
        return Response(LinkSerializer(link).data)


class LinkPermissionView(APIView):
    """The client toggles whether a coach may edit their prescriptions (vs read-only)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["coaching"], request=LinkPermissionSerializer, responses=LinkSerializer)
    def post(self, request, pk):
        link = get_object_or_404(CoachClientLink, pk=pk, client=request.user)
        ser = LinkPermissionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        link.can_edit_prescriptions = ser.validated_data["can_edit_prescriptions"]
        link.save(update_fields=["can_edit_prescriptions"])
        return Response(LinkSerializer(link).data)
