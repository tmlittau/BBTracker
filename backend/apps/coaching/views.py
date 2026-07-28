"""Coaching API: a coach's client list + per-client read overview, plus the
invite / accept / revoke lifecycle. All data access to a client's records goes
through an active CoachClientLink check (here and in `access.resolve_effective_owner`).
"""
from django.db.models import Count, Exists, OuterRef, Q
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

from .access import can_review_checkin
from .models import CheckInComment, CoachClientLink, LinkStatus
from .serializers import (
    CheckInCommentSerializer,
    CheckInReviewRowSerializer,
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
        coaches = (
            CoachClientLink.objects.filter(client=request.user, status=LinkStatus.ACTIVE)
            .select_related("coach", "client")
            .order_by("coach__email")
        )
        return Response(
            {
                "sent": LinkSerializer(sent, many=True).data,
                "received": LinkSerializer(received, many=True).data,
                "coaches": LinkSerializer(coaches, many=True).data,
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


def _check_in_dict(c):
    return {
        "id": c.id,
        "date": c.date,
        "bodyweight": float(c.bodyweight) if c.bodyweight is not None else None,
        "systolic": c.systolic,
        "diastolic": c.diastolic,
        "pulse": c.pulse,
        "energy": c.energy,
        "sleep": c.sleep,
        "mood": c.mood,
        "motivation": c.motivation,
        "soreness": c.soreness,
        "notes": c.notes,
    }


class CheckInReviewListView(APIView):
    """Coach's review queue: recent check-ins across all active clients, newest first.
    `?client=<id>` narrows to one client; `?status=pending` shows only those this coach
    hasn't commented on yet."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CheckInReviewRowSerializer(many=True))
    def get(self, request):
        if not getattr(request.user, "is_coach", False):
            raise PermissionDenied("Only coaches have a review queue.")
        client_ids = list(
            CoachClientLink.objects.filter(
                coach=request.user, status=LinkStatus.ACTIVE
            ).values_list("client_id", flat=True)
        )
        qs = CheckIn.objects.filter(owner_id__in=client_ids)
        client = request.query_params.get("client")
        if client:
            qs = qs.filter(owner_id=client)
        qs = (
            qs.select_related("owner")
            .annotate(
                n_comments=Count("comments", distinct=True),
                is_reviewed=Exists(
                    CheckInComment.objects.filter(
                        check_in=OuterRef("pk"), author=request.user
                    )
                ),
            )
            .order_by("-date")
        )
        if request.query_params.get("status") == "pending":
            qs = qs.filter(is_reviewed=False)
        rows = [
            {
                "id": c.id,
                "client_id": c.owner_id,
                "client_name": _name(c.owner),
                "date": c.date,
                "bodyweight": float(c.bodyweight) if c.bodyweight is not None else None,
                "energy": c.energy,
                "sleep": c.sleep,
                "has_notes": bool(c.notes and c.notes.strip()),
                "comment_count": c.n_comments,
                "reviewed": c.is_reviewed,
            }
            for c in qs[:100]
        ]
        return Response(CheckInReviewRowSerializer(rows, many=True).data)


class CheckInReviewDetailView(APIView):
    """One check-in with the surrounding week's aggregate + the feedback thread.
    Readable by the check-in's owner or a coach with an active link."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        check_in = get_object_or_404(CheckIn.objects.select_related("owner"), pk=pk)
        if not can_review_checkin(request.user, check_in):
            raise PermissionDenied("You can't view this check-in.")
        client = check_in.owner
        series = list(
            CheckIn.objects.filter(owner=client, date__lte=check_in.date)
            .order_by("-date")
            .values("date", "bodyweight")[:10]
        )
        series.reverse()
        prev = (
            CheckIn.objects.filter(
                owner=client, date__lt=check_in.date, bodyweight__isnull=False
            )
            .order_by("-date")
            .first()
        )
        comments = check_in.comments.select_related("author").all()
        return Response(
            {
                "check_in": _check_in_dict(check_in),
                "client": {"id": client.id, "name": _name(client), "email": client.email},
                "previous_bodyweight": float(prev.bodyweight) if prev else None,
                "weight_series": [
                    {
                        "date": s["date"],
                        "bodyweight": (
                            float(s["bodyweight"]) if s["bodyweight"] is not None else None
                        ),
                    }
                    for s in series
                ],
                "weekly": weekly_checkin(client, check_in.date),
                "comments": CheckInCommentSerializer(comments, many=True).data,
            }
        )


class CheckInCommentCreateView(APIView):
    """Add feedback to a check-in (coach) or reply (client). Author is the requester."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=CheckInCommentSerializer, responses=CheckInCommentSerializer)
    def post(self, request, pk):
        check_in = get_object_or_404(CheckIn, pk=pk)
        if not can_review_checkin(request.user, check_in):
            raise PermissionDenied("You can't comment on this check-in.")
        body = (request.data.get("body") or "").strip()
        if not body:
            raise ValidationError({"body": "Feedback can't be empty."})
        comment = CheckInComment.objects.create(
            check_in=check_in, author=request.user, body=body
        )
        return Response(
            CheckInCommentSerializer(comment).data, status=status.HTTP_201_CREATED
        )


class TemplateApplyView(APIView):
    """Deep-copy one of the coach's own templates (a program / protocol / meal plan
    they own) onto a client. Requires an active link with edit access."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["coaching"], responses=OpenApiTypes.OBJECT)
    def post(self, request):
        from .services import apply_template

        if not getattr(request.user, "is_coach", False):
            raise PermissionDenied("Only coaches can apply templates.")
        client_id = request.data.get("client")
        link = CoachClientLink.active_link(request.user, client_id) if client_id else None
        if link is None:
            raise PermissionDenied("You do not have an active coaching link with that client.")
        if not link.can_edit_prescriptions:
            raise PermissionDenied("You don't have edit access to this client's plan.")
        new = apply_template(
            request.user, request.data.get("kind"), request.data.get("id"), link.client
        )
        return Response(
            {"id": new.id, "name": new.name}, status=status.HTTP_201_CREATED
        )
