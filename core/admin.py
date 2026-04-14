from django.contrib import admin
from .models import Project, Task, Channel, Message, Feedback

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'owner', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)
    filter_horizontal = ('members',)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'project', 'status', 'priority', 'assignee', 'is_approved', 'created_at')
    list_filter = ('status', 'priority', 'is_approved', 'created_at')
    search_fields = ('title', 'description')
    autocomplete_fields = ('project', 'assignee', 'created_by')

@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'project', 'created_at')
    search_fields = ('name',)
    list_filter = ('created_at',)
    filter_horizontal = ('members',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'channel', 'sender', 'created_at', 'short_content')
    list_filter = ('channel', 'created_at')
    search_fields = ('content', 'sender__username')

    def short_content(self, obj):
        return obj.content[:30] + '...' if len(obj.content) > 30 else obj.content
    short_content.short_description = 'Content'

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'created_at', 'short_content')
    list_filter = ('created_at', 'project')
    search_fields = ('content',)

    def short_content(self, obj):
        return obj.content[:30] + '...' if len(obj.content) > 30 else obj.content
    short_content.short_description = 'Content'

