from datetime import datetime
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.response import Response

from cinema.models import Cinema
from cinema.schema import cinema_schema
from movies.schema import ensure_movie_table
from movies.models import Movie
from shows.models import Screen, Seat, Show

from .models import Booking, BookingSeat
from .permissions import BookingCustomerPermission
from .schema import ensure_booking_tables
from .serializers import (
    BookingCreateSerializer,
    BookingSerializer,
)
from .services import (
    BOOKING_HOLD_DURATION,
    expire_holds_for_cinema,
    expire_holds_for_show,
)


class SeatUnavailable(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "One or more selected seats are no longer available."
    default_code = "seat_unavailable"


class BookingHoldExpired(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = "This seat hold has expired. Please select your seats again."
    default_code = "booking_hold_expired"


def prepare_booking_schema(cinema):
    ensure_movie_table(cinema.schema_name)
    ensure_booking_tables(cinema.schema_name)


def get_active_cinema(slug):
    cinema = Cinema.objects.filter(
        slug=slug,
        status=Cinema.Status.ACTIVE,
    ).first()
    if cinema is None:
        raise NotFound("Active cinema not found.")
    return cinema


def show_has_started(show):
    local_start = timezone.make_aware(
        datetime.combine(show.show_date, show.start_time),
        timezone.get_current_timezone(),
    )
    return local_start <= timezone.now()


def get_user_bookings(user, request=None):
    results = []
    cinemas = Cinema.objects.all().order_by("pk")
    for cinema in cinemas:
        prepare_booking_schema(cinema)
        with cinema_schema(cinema.schema_name), transaction.atomic():
            expire_holds_for_cinema()
            bookings = (
                Booking.objects.filter(user=user)
                .select_related(
                    "show__movie",
                    "show__screen__cinema",
                )
                .prefetch_related("booking_seats__seat")
            )
            results.extend(
                (
                    booking.created_at,
                    BookingSerializer(
                        booking,
                        context={"request": request},
                    ).data,
                )
                for booking in bookings
            )
    results.sort(key=lambda item: item[0], reverse=True)
    return [data for _, data in results]


def create_booking(request, *, hold):
    serializer = BookingCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    cinema = get_active_cinema(serializer.validated_data["cinema_slug"])
    prepare_booking_schema(cinema)

    try:
        with cinema_schema(cinema.schema_name), transaction.atomic():
            try:
                show = Show.objects.select_for_update().get(
                    pk=serializer.validated_data["show"]
                )
            except Show.DoesNotExist:
                raise NotFound("Active show not found.")

            expire_holds_for_show(show)
            screen = Screen.objects.filter(
                pk=show.screen_id,
                cinema_id=cinema.pk,
            ).first()
            movie = Movie.objects.filter(
                pk=show.movie_id,
                cinema_id=cinema.pk,
                status=Movie.Status.ACTIVE,
            ).first()
            if screen is None or movie is None:
                raise NotFound("Active show not found.")
            if show_has_started(show):
                raise ValidationError({"show": "This show has already started."})

            selected_ids = serializer.validated_data["seats"]
            seats = list(
                Seat.objects.select_for_update()
                .filter(screen_id=show.screen_id, pk__in=selected_ids)
                .order_by("pk")
            )
            if len(seats) != len(selected_ids):
                raise ValidationError(
                    {"seats": "One or more seats do not belong to this show."}
                )

            prices = dict(show.seat_prices.values_list("seat_type", "price"))
            if any(seat.seat_type not in prices for seat in seats):
                raise ValidationError(
                    {"show": "The show is missing prices for selected seat types."}
                )

            already_reserved = set(
                BookingSeat.objects.filter(
                    show=show,
                    seat_id__in=selected_ids,
                    is_active=True,
                ).values_list("seat_id", flat=True)
            )
            if already_reserved:
                raise SeatUnavailable()

            total = sum(
                (prices[seat.seat_type] for seat in seats),
                Decimal("0.00"),
            )
            booking = Booking.objects.create(
                user=request.user,
                show=show,
                total_amount=total,
                status=Booking.Status.HELD if hold else Booking.Status.CONFIRMED,
                hold_expires_at=(
                    timezone.now() + BOOKING_HOLD_DURATION if hold else None
                ),
            )
            BookingSeat.objects.bulk_create(
                [
                    BookingSeat(
                        booking=booking,
                        show=show,
                        seat=seat,
                        price_at_booking=prices[seat.seat_type],
                    )
                    for seat in seats
                ]
            )
            response_data = BookingSerializer(
                booking,
                context={"request": request},
            ).data
    except IntegrityError as error:
        cause = error.__cause__
        constraint_name = getattr(
            getattr(cause, "diag", None),
            "constraint_name",
            None,
        )
        if constraint_name != "unique_active_show_seat_booking":
            raise
        raise SeatUnavailable() from error

    return Response(
        response_data,
        status=status.HTTP_201_CREATED,
    )


class BookingListCreateView(generics.GenericAPIView):
    permission_classes = [BookingCustomerPermission]

    def get(self, request):
        return Response(get_user_bookings(request.user, request))

    def post(self, request):
        return create_booking(request, hold=False)


class BookingHoldCreateView(generics.GenericAPIView):
    permission_classes = [BookingCustomerPermission]

    def post(self, request):
        return create_booking(request, hold=True)


class BookingConfirmView(generics.GenericAPIView):
    permission_classes = [BookingCustomerPermission]

    def post(self, request, pk):
        for cinema in Cinema.objects.all().order_by("pk"):
            prepare_booking_schema(cinema)
            with cinema_schema(cinema.schema_name), transaction.atomic():
                show_id = (
                    Booking.objects.filter(pk=pk, user=request.user)
                    .values_list("show_id", flat=True)
                    .first()
                )
                if show_id is None:
                    continue

                try:
                    show = Show.objects.select_for_update().get(pk=show_id)
                except Show.DoesNotExist:
                    continue
                expire_holds_for_show(show)
                booking = (
                    Booking.objects.select_for_update()
                    .filter(pk=pk, user=request.user)
                    .select_related("show__movie", "show__screen__cinema")
                    .prefetch_related("booking_seats__seat")
                    .first()
                )
                if booking is None:
                    continue
                if booking.status == Booking.Status.EXPIRED:
                    raise BookingHoldExpired()
                if booking.status != Booking.Status.HELD:
                    raise ValidationError(
                        {"status": "Only an active seat hold can be confirmed."}
                    )

                booking.status = Booking.Status.CONFIRMED
                booking.save(update_fields=("status",))
                return Response(
                    BookingSerializer(
                        booking,
                        context={"request": request},
                    ).data
                )
        raise NotFound("Booking hold not found.")


class MyBookingListView(generics.GenericAPIView):
    permission_classes = [BookingCustomerPermission]

    def get(self, request):
        return Response(get_user_bookings(request.user, request))


class BookingDetailView(generics.GenericAPIView):
    permission_classes = [BookingCustomerPermission]

    def get(self, request, pk):
        for cinema in Cinema.objects.all().order_by("pk"):
            prepare_booking_schema(cinema)
            with cinema_schema(cinema.schema_name), transaction.atomic():
                expire_holds_for_cinema()
                booking = (
                    Booking.objects.filter(pk=pk, user=request.user)
                    .select_related(
                        "show__movie",
                        "show__screen__cinema",
                    )
                    .prefetch_related("booking_seats__seat")
                    .first()
                )
                if booking is not None:
                    return Response(
                        BookingSerializer(
                            booking,
                            context={"request": request},
                        ).data
                    )
        raise NotFound("Booking not found.")


class BookingCancelView(generics.GenericAPIView):
    permission_classes = [BookingCustomerPermission]

    def post(self, request, pk):
        for cinema in Cinema.objects.all().order_by("pk"):
            prepare_booking_schema(cinema)
            with cinema_schema(cinema.schema_name), transaction.atomic():
                expire_holds_for_cinema()
                booking = (
                    Booking.objects.select_for_update()
                    .filter(pk=pk, user=request.user)
                    .select_related("show__movie", "show__screen__cinema")
                    .first()
                )
                if booking is None:
                    continue
                if booking.status == Booking.Status.CANCELLED:
                    raise ValidationError(
                        {"status": "This booking has already been cancelled."}
                    )
                if booking.status == Booking.Status.EXPIRED:
                    raise BookingHoldExpired()
                if show_has_started(booking.show):
                    raise ValidationError(
                        {"booking": "A booking cannot be cancelled after the show starts."}
                    )

                booking.status = Booking.Status.CANCELLED
                booking.save(update_fields=("status",))
                booking.booking_seats.update(is_active=False)
                return Response(
                    BookingSerializer(
                        booking,
                        context={"request": request},
                    ).data
                )
        raise NotFound("Booking not found.")
