from django.urls import path

from .views import CSRFView, MeView

urlpatterns = [
    path("csrf/", CSRFView.as_view(), name="auth-csrf"),
    path("me/", MeView.as_view(), name="auth-me"),
]
