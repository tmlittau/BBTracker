from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # django-allauth headless API (session/browser flavour): /_allauth/browser/v1/...
    path("_allauth/", include("allauth.headless.urls")),
    # App API
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/training/", include("apps.training.urls")),
    path("api/v1/nutrition/", include("apps.nutrition.urls")),
    path("api/v1/protocols/", include("apps.protocols.urls")),
    path("api/v1/diary/", include("apps.diary.urls")),
    # OpenAPI schema + docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
