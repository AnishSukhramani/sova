"""
Foundation models for Sova. Every other app references these.

    SubFragmentRunLog — health/state of each collector (one row per collector)
    Practice          — master practice record, NPI as primary key
    Signal            — central signal store with decay metadata
    LeadScore         — versioned scoring output (is_latest flag for the current row)
"""

from django.db import models


class SubFragmentRunLog(models.Model):
    name = models.CharField(max_length=100, unique=True)
    last_run_at = models.DateTimeField(null=True)
    last_run_status = models.CharField(max_length=20, default='never_run')
    records_written = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    expected_interval_hours = models.IntegerField(default=24)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sub_fragment_run_log'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['last_run_status']),
        ]

    def __str__(self) -> str:
        return f'{self.name} [{self.last_run_status}]'


class Practice(models.Model):
    npi = models.CharField(max_length=10, primary_key=True)
    practice_name = models.CharField(max_length=255)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    specialty_taxonomy_code = models.CharField(max_length=20, blank=True)
    specialty_display = models.CharField(max_length=100, blank=True)
    practice_type = models.CharField(max_length=20, blank=True)   # solo / group
    entity_type = models.CharField(max_length=20, blank=True)     # individual / organization
    website_url = models.CharField(max_length=500, blank=True)
    domain = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_current_client = models.BooleanField(default=False)
    is_oig_excluded = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'practices'
        indexes = [
            models.Index(fields=['state']),
            models.Index(fields=['zip_code']),
            models.Index(fields=['specialty_taxonomy_code']),
            models.Index(fields=['is_active']),
            models.Index(fields=['practice_type']),
            models.Index(fields=['state', 'is_active']),
        ]

    def __str__(self) -> str:
        return f'{self.npi} — {self.practice_name}'


class Signal(models.Model):
    """A single observed signal about a practice (job posting, review, lifecycle event, etc.)."""

    id = models.BigAutoField(primary_key=True)
    practice = models.ForeignKey(
        Practice, on_delete=models.CASCADE, related_name='signals', db_index=True,
    )
    signal_type = models.CharField(max_length=50, db_index=True)
    signal_source = models.CharField(max_length=50)
    raw_value = models.FloatField()
    confidence = models.CharField(max_length=10)  # High / Moderate / Low
    evidence_count = models.IntegerField(default=1)
    evidence_summary = models.TextField(blank=True)
    half_life_days = models.IntegerField()
    collected_at = models.DateTimeField(db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'signals'
        indexes = [
            models.Index(fields=['practice', 'signal_type', 'collected_at']),
        ]

    def __str__(self) -> str:
        return f'{self.signal_type} for {self.practice_id} @ {self.collected_at:%Y-%m-%d}'


class LeadScore(models.Model):
    """Versioned scoring output. New scores append; only one row per practice has is_latest=True."""

    id = models.BigAutoField(primary_key=True)
    practice = models.ForeignKey(
        Practice, on_delete=models.CASCADE, related_name='lead_scores',
    )
    composite_score = models.FloatField()
    fit_score = models.FloatField(null=True, blank=True)
    operational_pain_score = models.FloatField(null=True, blank=True)
    timing_score = models.FloatField(null=True, blank=True)
    first_party_intent_score = models.FloatField(null=True, blank=True)
    technographic_score = models.FloatField(null=True, blank=True)
    human_route_score = models.FloatField(null=True, blank=True)
    geography_score = models.FloatField(null=True, blank=True)
    tier = models.CharField(max_length=10)  # HOT / WARM / COLD
    modifiers_applied = models.JSONField(default=list)
    signals_summary = models.JSONField(default=dict)
    hot_qualification = models.JSONField(default=dict)
    scored_at = models.DateTimeField(db_index=True)
    is_latest = models.BooleanField(default=True)

    class Meta:
        db_table = 'lead_scores'
        indexes = [
            models.Index(fields=['practice', 'is_latest']),
            models.Index(fields=['tier', 'is_latest']),
            models.Index(fields=['scored_at']),
        ]

    def __str__(self) -> str:
        return f'{self.practice_id} score={self.composite_score:.1f} ({self.tier})'
