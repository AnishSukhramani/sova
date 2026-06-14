"""
Orchestrator models — conversation state and task-run tracking.

SovaConversation persists chatbot threads (Phase 10).
SovaTaskRun persists every long-running tool invocation so clients can poll
for status and we can cancel mid-flight.
"""

import uuid

from django.db import models


class SovaConversation(models.Model):
    conversation_id = models.UUIDField(default=uuid.uuid4, unique=True)
    thread_id = models.CharField(max_length=255, unique=True)
    user_identifier = models.CharField(max_length=255)
    messages = models.JSONField(default=list)
    mode = models.CharField(max_length=50, default='chatbot')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sova_conversations'

    def __str__(self) -> str:
        return f'{self.thread_id} ({self.mode})'


class SovaTaskRun(models.Model):
    run_id = models.UUIDField(default=uuid.uuid4, unique=True)
    conversation = models.ForeignKey(
        SovaConversation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_runs',
    )
    task_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default='pending')  # pending/running/completed/failed/cancelled
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    progress = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sova_task_runs'

    def __str__(self) -> str:
        return f'{self.task_name} [{self.status}] {self.run_id}'
