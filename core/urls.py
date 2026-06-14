"""URL routes for the `core` app."""

from django.urls import path

from .views import PracticeDetailView, PracticeListView, SystemHealthView

app_name = 'core'

urlpatterns = [
    path('health/', SystemHealthView.as_view(), name='health'),
    path('practices/', PracticeListView.as_view(), name='practice-list'),
    path('practices/<str:npi>/', PracticeDetailView.as_view(), name='practice-detail'),
]
