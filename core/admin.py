from django.contrib import admin

from .models import LeadScore, Practice, Signal, SubFragmentRunLog


@admin.register(SubFragmentRunLog)
class SubFragmentRunLogAdmin(admin.ModelAdmin):
    list_display = ('name', 'last_run_status', 'records_written', 'last_run_at', 'expected_interval_hours')
    list_filter = ('last_run_status',)
    search_fields = ('name',)
    ordering = ('-last_run_at',)


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
    list_display = ('npi', 'practice_name', 'city', 'state', 'specialty_display', 'is_active', 'is_current_client')
    list_filter = ('state', 'is_active', 'is_current_client', 'practice_type', 'entity_type', 'is_oig_excluded')
    search_fields = ('npi', 'practice_name', 'city', 'zip_code', 'domain')


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ('signal_type', 'signal_source', 'practice', 'raw_value', 'confidence', 'collected_at')
    list_filter = ('signal_type', 'confidence', 'signal_source')
    search_fields = ('practice__npi', 'practice__practice_name')
    date_hierarchy = 'collected_at'


@admin.register(LeadScore)
class LeadScoreAdmin(admin.ModelAdmin):
    list_display = ('practice', 'composite_score', 'tier', 'is_latest', 'scored_at')
    list_filter = ('tier', 'is_latest')
    search_fields = ('practice__npi', 'practice__practice_name')
    date_hierarchy = 'scored_at'
