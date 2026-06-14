"""URL routes for the `orchestrator` app."""

from django.urls import path

from .views import CollectorHealthView, TaskCancelView, TaskStatusView

app_name = 'orchestrator'

urlpatterns = [
    path('health/collectors/', CollectorHealthView.as_view(), name='health-collectors'),
    path('tasks/<uuid:run_id>/', TaskStatusView.as_view(), name='task-status'),
    path('tasks/<uuid:run_id>/cancel/', TaskCancelView.as_view(), name='task-cancel'),
]
