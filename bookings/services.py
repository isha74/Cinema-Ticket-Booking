from datetime import timedelta

from django.utils import timezone

from .models import Booking, BookingSeat


BOOKING_HOLD_DURATION = timedelta(minutes=5)


def expire_holds_for_show(show, now=None):
    now = now or timezone.now()
    expired_ids = list(
        Booking.objects.filter(
            show=show,
            status=Booking.Status.HELD,
            hold_expires_at__lte=now,
        ).values_list("pk", flat=True)
    )
    if not expired_ids:
        return

    BookingSeat.objects.filter(
        booking_id__in=expired_ids,
        is_active=True,
    ).update(is_active=False)
    Booking.objects.filter(pk__in=expired_ids).update(
        status=Booking.Status.EXPIRED,
    )


def expire_holds_for_cinema(now=None):
    now = now or timezone.now()
    expired_ids = list(
        Booking.objects.filter(
            status=Booking.Status.HELD,
            hold_expires_at__lte=now,
        ).values_list("pk", flat=True)
    )
    if not expired_ids:
        return

    BookingSeat.objects.filter(
        booking_id__in=expired_ids,
        is_active=True,
    ).update(is_active=False)
    Booking.objects.filter(pk__in=expired_ids).update(
        status=Booking.Status.EXPIRED,
    )


def seat_statuses_for_show(show, now=None):
    now = now or timezone.now()
    statuses = {}
    reservations = BookingSeat.objects.filter(
        show=show,
        is_active=True,
    ).select_related("booking")

    for reservation in reservations:
        booking = reservation.booking
        if booking.status == Booking.Status.CONFIRMED:
            statuses[reservation.seat_id] = "BOOKED"
        elif (
            booking.status == Booking.Status.HELD
            and booking.hold_expires_at is not None
            and booking.hold_expires_at > now
        ):
            statuses[reservation.seat_id] = "HELD"

    return statuses
