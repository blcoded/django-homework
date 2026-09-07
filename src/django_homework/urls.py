"""
URL configuration for django_homework project.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path



def home(request):
    """Root entrypoint view returning basic API metadata."""
    return JsonResponse(
        {
            "name": "Shared Household Chores API",
            "status": "online",
            "version": "0.1.0",
        }
    )


def health_check(request):
    """Health check endpoint for container and uptime monitoring."""
    return JsonResponse({"status": "ok", "message": "Shared Household Chores API"})


urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/auth/", include("users.urls")),
    path("api/households/", include("households.urls")),
    path("api/chores/", include("chores.urls")),
]



