from django.urls import path

from .views import (
    CheckInCommentCreateView,
    CheckInReviewDetailView,
    CheckInReviewListView,
    ClientOverviewView,
    CoachClientListView,
    InviteListCreateView,
    InviteRespondView,
    LinkPermissionView,
    LinkRevokeView,
    TemplateApplyView,
)

urlpatterns = [
    path("clients/", CoachClientListView.as_view(), name="coaching-clients"),
    path(
        "clients/<int:client_id>/overview/",
        ClientOverviewView.as_view(),
        name="coaching-client-overview",
    ),
    path("check-ins/", CheckInReviewListView.as_view(), name="coaching-checkins"),
    path("check-ins/<int:pk>/", CheckInReviewDetailView.as_view(), name="coaching-checkin-detail"),
    path(
        "check-ins/<int:pk>/comments/",
        CheckInCommentCreateView.as_view(),
        name="coaching-checkin-comment",
    ),
    path("templates/apply/", TemplateApplyView.as_view(), name="coaching-template-apply"),
    path("invites/", InviteListCreateView.as_view(), name="coaching-invites"),
    path("invites/<int:pk>/respond/", InviteRespondView.as_view(), name="coaching-invite-respond"),
    path("links/<int:pk>/revoke/", LinkRevokeView.as_view(), name="coaching-link-revoke"),
    path(
        "links/<int:pk>/permission/",
        LinkPermissionView.as_view(),
        name="coaching-link-permission",
    ),
]
