from django.urls import path

from .views import (
    ClientOverviewView,
    CoachClientListView,
    InviteListCreateView,
    InviteRespondView,
    LinkPermissionView,
    LinkRevokeView,
)

urlpatterns = [
    path("clients/", CoachClientListView.as_view(), name="coaching-clients"),
    path(
        "clients/<int:client_id>/overview/",
        ClientOverviewView.as_view(),
        name="coaching-client-overview",
    ),
    path("invites/", InviteListCreateView.as_view(), name="coaching-invites"),
    path("invites/<int:pk>/respond/", InviteRespondView.as_view(), name="coaching-invite-respond"),
    path("links/<int:pk>/revoke/", LinkRevokeView.as_view(), name="coaching-link-revoke"),
    path(
        "links/<int:pk>/permission/",
        LinkPermissionView.as_view(),
        name="coaching-link-permission",
    ),
]
