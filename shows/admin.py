from django.contrib import admin

from .models import Screen, Seat


class SeatInline(admin.TabularInline):
    model = Seat
    extra = 0


@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    list_display = ("name", "cinema", "total_seats", "created_at")
    list_filter = ("cinema",)
    search_fields = ("name", "cinema__name")
    inlines = (SeatInline,)


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("seat_number", "row", "screen", "seat_type")
    list_filter = ("seat_type", "screen__cinema")
    search_fields = ("seat_number", "row", "screen__name", "screen__cinema__name")
