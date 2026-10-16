import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

import bookings.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("authentication", "0002_alter_user_managers"),
        ("shows", "0004_shows_and_show_seat_prices"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Booking",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        (
                            "booking_reference",
                            models.CharField(
                                default=bookings.models.generate_booking_reference,
                                editable=False,
                                max_length=27,
                                unique=True,
                            ),
                        ),
                        (
                            "total_amount",
                            models.DecimalField(decimal_places=2, max_digits=10),
                        ),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("CONFIRMED", "Confirmed"),
                                    ("CANCELLED", "Cancelled"),
                                ],
                                default="CONFIRMED",
                                max_length=20,
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "show",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="bookings",
                                to="shows.show",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="bookings",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={"ordering": ["-created_at"]},
                ),
                migrations.CreateModel(
                    name="BookingSeat",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "price_at_booking",
                            models.DecimalField(decimal_places=2, max_digits=8),
                        ),
                        ("is_active", models.BooleanField(default=True)),
                        (
                            "booking",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="booking_seats",
                                to="bookings.booking",
                            ),
                        ),
                        (
                            "seat",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="booking_records",
                                to="shows.seat",
                            ),
                        ),
                        (
                            "show",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="reserved_seats",
                                to="shows.show",
                            ),
                        ),
                    ],
                    options={
                        "indexes": [
                            models.Index(
                                fields=["booking"],
                                name="booking_seat_booking_idx",
                            ),
                        ],
                        "constraints": [
                            models.UniqueConstraint(
                                condition=Q(("is_active", True)),
                                fields=("show", "seat"),
                                name="unique_active_show_seat_booking",
                            ),
                            models.CheckConstraint(
                                condition=Q(("price_at_booking__gt", 0)),
                                name="booking_seat_price_positive",
                            ),
                        ],
                    },
                ),
            ],
        ),
    ]
