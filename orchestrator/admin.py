from django.contrib import admin

from .models import SovaConversation, SovaTaskRun


@admin.register(SovaConversation)
class SovaConversationAdmin(admin.ModelAdmin):
    list_display = ('thread_id', 'user_identifier', 'mode', 'created_at', 'updated_at')
    list_filter = ('mode',)
    search_fields = ('thread_id', 'user_identifier')


@admin.register(SovaTaskRun)
class SovaTaskRunAdmin(admin.ModelAdmin):
    list_display = ('run_id', 'task_name', 'status', 'created_at', 'completed_at')
    list_filter = ('status', 'task_name')
    search_fields = ('run_id', 'task_name')
    date_hierarchy = 'created_at'
