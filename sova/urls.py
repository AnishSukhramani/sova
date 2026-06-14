"""
Top-level URL configuration for the Sova project.

Routing:
    /admin/        — Django admin UI
    /api/v1/...    — versioned REST API, delegated to each app's urls.py
    /api/docs/     — Swagger UI (drf-yasg)
    /api/redoc/    — ReDoc (drf-yasg)
"""

from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework.permissions import AllowAny

schema_view = get_schema_view(
    openapi.Info(
        title='Sova API',
        default_version='v1',
        description='Marketing intelligence backend for Neurality Health.',
    ),
    public=True,
    permission_classes=[AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('core.urls', namespace='core')),
    path('api/v1/', include('tools.urls', namespace='tools')),
    path('api/v1/', include('orchestrator.urls', namespace='orchestrator')),
    path('api/v1/', include('chatbot.urls', namespace='chatbot')),
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='swagger'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='redoc'),
]
