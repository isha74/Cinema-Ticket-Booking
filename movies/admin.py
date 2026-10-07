from django.contrib import admin

from .models import Movie


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("title", "cinema", "language", "genre", "release_date", "status", "created_at")
    list_filter = ("status", "language", "genre", "release_date")
    search_fields = ("title", "cinema__name", "language", "genre")
