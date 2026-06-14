from rest_framework import serializers

from .models import SovaTaskRun


class SovaTaskRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = SovaTaskRun
        fields = '__all__'


class TaskStatusSerializer(serializers.ModelSerializer):
    """Lightweight status view — what a polling client needs."""

    class Meta:
        model = SovaTaskRun
        fields = ('run_id', 'status', 'progress', 'result', 'error', 'created_at', 'completed_at')
