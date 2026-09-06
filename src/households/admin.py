from django.contrib import admin
from .models import Household, HouseholdMember


class HouseholdMemberInline(admin.TabularInline):
    model = HouseholdMember
    extra = 0


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("name", "timezone", "invite_code", "created_at")
    search_fields = ("name", "invite_code")
    inlines = [HouseholdMemberInline]


@admin.register(HouseholdMember)
class HouseholdMemberAdmin(admin.ModelAdmin):
    list_display = ("household", "user", "status", "joined_at")
    list_filter = ("status", "household")
    search_fields = ("user__email", "user__display_name", "household__name")
