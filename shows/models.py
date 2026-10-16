from django.db import models
from django.db.models import Q

from cinema.models import Cinema
from movies.models import Movie


class Screen(models.Model):
    cinema = models.ForeignKey(
        Cinema,
        on_delete=models.DO_NOTHING,
        related_name="screens",
    )
    name = models.CharField(max_length=100)
    total_seats = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cinema__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=("cinema", "name"),
                name="unique_screen_name_per_cinema",
            )
        ]

    def __str__(self):
        return f"{self.cinema.name} - {self.name}"


class Seat(models.Model):
    class SeatType(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        GOLD = "GOLD", "Gold"
        PREMIUM = "PREMIUM", "Premium"
        RECLINER = "RECLINER", "Recliner"

    screen = models.ForeignKey(
        Screen,
        on_delete=models.CASCADE,
        related_name="seats",
    )
    seat_number = models.CharField(max_length=10)
    row = models.CharField(max_length=10)
    position = models.PositiveSmallIntegerField(null=True, blank=True)
    seat_type = models.CharField(
        max_length=20,
        choices=SeatType.choices,
        default=SeatType.NORMAL,
    )

    class Meta:
        ordering = ["row", "position", "seat_number"]
        constraints = [
            models.UniqueConstraint(
                fields=("screen", "seat_number"),
                name="unique_seat_number_per_screen",
            ),
            models.UniqueConstraint(
                fields=("screen", "row", "position"),
                condition=models.Q(position__isnull=False),
                name="unique_seat_position_per_row",
            ),
        ]

    def __str__(self):
        return f"{self.screen.name} - {self.seat_number}"


class Show(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="shows",
    )
    screen = models.ForeignKey(
        Screen,
        on_delete=models.CASCADE,
        related_name="shows",
    )
    show_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["show_date", "start_time", "screen_id"]
        constraints = [
            models.UniqueConstraint(
                fields=("screen", "show_date", "start_time"),
                name="unique_show_start_per_screen",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=models.F("start_time")),
                name="show_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.movie.title} at {self.screen.name} on {self.show_date}"


class ShowSeatPrice(models.Model):
    show = models.ForeignKey(
        Show,
        on_delete=models.CASCADE,
        related_name="seat_prices",
    )
    seat_type = models.CharField(max_length=20, choices=Seat.SeatType.choices)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ["seat_type"]
        constraints = [
            models.UniqueConstraint(
                fields=("show", "seat_type"),
                name="unique_show_seat_type_price",
            ),
            models.CheckConstraint(
                condition=Q(price__gt=0),
                name="show_seat_price_positive",
            ),
        ]

    def __str__(self):
        return f"{self.show} - {self.seat_type}: {self.price}"
