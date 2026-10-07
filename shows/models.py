from django.db import models

from cinema.models import Cinema


class Screen(models.Model):
    cinema = models.ForeignKey(
        Cinema,
        on_delete=models.CASCADE,
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
        STANDARD = "STANDARD", "Standard"
        PREMIUM = "PREMIUM", "Premium"

    screen = models.ForeignKey(
        Screen,
        on_delete=models.CASCADE,
        related_name="seats",
    )
    seat_number = models.CharField(max_length=10)
    row = models.CharField(max_length=10)
    seat_type = models.CharField(
        max_length=20,
        choices=SeatType.choices,
        default=SeatType.STANDARD,
    )

    class Meta:
        ordering = ["row", "seat_number"]
        constraints = [
            models.UniqueConstraint(
                fields=("screen", "seat_number"),
                name="unique_seat_number_per_screen",
            )
        ]

    def __str__(self):
        return f"{self.screen.name} - {self.seat_number}"
