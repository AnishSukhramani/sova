"""
Collector output models.

Each external data source gets its own table. This is the "database-as-bus"
pattern — collectors never call each other; downstream tools read from these
tables.
"""

from django.db import models

from core.models import Practice


class GooglePlacesData(models.Model):
    """Per-practice Google Places snapshot — reviews, ratings, hours, friction signals."""

    id = models.BigAutoField(primary_key=True)
    practice = models.ForeignKey(
        Practice, on_delete=models.CASCADE, related_name='google_places_data',
    )
    google_place_id = models.CharField(max_length=255, blank=True)
    review_count = models.IntegerField(null=True, blank=True)
    star_rating = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    review_velocity_30d = models.FloatField(null=True, blank=True)
    phone_friction_count = models.IntegerField(default=0)
    phone_friction_keywords = models.JSONField(default=list, blank=True)
    opening_hours = models.JSONField(null=True, blank=True)
    hours_changed = models.BooleanField(default=False)
    hours_change_type = models.CharField(max_length=20, blank=True, null=True)
    response_rate = models.FloatField(null=True, blank=True)
    collected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'google_places_data'
        indexes = [
            models.Index(fields=['practice', 'collected_at']),
        ]

    def __str__(self) -> str:
        return f'GooglePlaces[{self.practice_id}] @ {self.collected_at:%Y-%m-%d}'
