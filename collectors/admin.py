from django.contrib import admin

from .models import GooglePlacesData


@admin.register(GooglePlacesData)
class GooglePlacesDataAdmin(admin.ModelAdmin):
    list_display = (
        'practice', 'star_rating', 'review_count',
        'phone_friction_count', 'collected_at',
    )
    list_filter = ('hours_changed', 'hours_change_type')
    search_fields = ('practice__npi', 'practice__practice_name', 'google_place_id')
    date_hierarchy = 'collected_at'
