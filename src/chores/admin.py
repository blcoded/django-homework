from django.contrib import admin
from .models import Chore


@admin.register(Chore)
class ChoreAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "household",
        "effort_level",
        "recurrence_type",
        "deadline_mode",
        "is_multi_assignee",
        "is_archived",
    )
    list_filter = (
        "effort_level",
        "recurrence_type",
        "deadline_mode",
        "is_multi_assignee",
        "is_archived",
        "household",
    )
    search_fields = ("title", "description", "household__name")
