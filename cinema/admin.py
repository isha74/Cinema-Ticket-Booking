from django.contrib import admin

from .models import Cinema


@admin.register(Cinema)
class CinemaAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "schema_name", "status", "owner", "city", "created_at")
    search_fields = ("name", "domain", "schema_name", "owner__username", "owner__email", "city")
    list_filter = ("status", "city", "created_at")
