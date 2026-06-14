"""DRF serializers for core models."""

from rest_framework import serializers

from .models import LeadScore, Practice, Signal, SubFragmentRunLog


class PracticeListSerializer(serializers.ModelSerializer):
    """Light fields for list endpoints."""

    class Meta:
        model = Practice
        fields = (
            'npi', 'practice_name', 'city', 'state',
            'specialty_display', 'is_active', 'is_current_client',
        )


class PracticeDetailSerializer(serializers.ModelSerializer):
    """Full fields for detail endpoints."""

    class Meta:
        model = Practice
        fields = '__all__'


class SubFragmentRunLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubFragmentRunLog
        fields = '__all__'


class SignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signal
        fields = '__all__'


class LeadScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadScore
        fields = '__all__'
