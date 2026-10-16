import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from shows.models import Seat, Show


def generate_booking_reference():
    return f"CB-{uuid.uuid4().hex[:24].upper()}"


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    show = models.ForeignKey(
        Show,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    booking_reference = models.CharField(
        max_length=27,
        unique=True,
        default=generate_booking_reference,
        editable=False,
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.booking_reference


class BookingSeat(models.Model):
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="booking_seats",
    )
    show = models.ForeignKey(
        Show,
        on_delete=models.PROTECT,
        related_name="reserved_seats",
    )
    seat = models.ForeignKey(
        Seat,
        on_delete=models.PROTECT,
        related_name="booking_records",
    )
    price_at_booking = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("show", "seat"),
                condition=Q(is_active=True),
                name="unique_active_show_seat_booking",
            ),
            models.CheckConstraint(
                condition=Q(price_at_booking__gt=0),
                name="booking_seat_price_positive",
            ),
        ]
        indexes = [
            models.Index(fields=("booking",), name="booking_seat_booking_idx"),
        ]
