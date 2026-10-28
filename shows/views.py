from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from bookings.services import expire_holds_for_show, seat_statuses_for_show
from cinema.models import Cinema
from movies.models import Movie
from movies.schema import ensure_movie_table, movie_table_exists

from .models import Screen, Seat, Show, ShowSeatPrice
from .permissions import (
    ScreenListCreatePermission,
    ScreenObjectPermission,
    SeatListCreatePermission,
    ShowListCreatePermission,
    ShowSeatAvailabilityPermission,
)
from .schema import cinema_schema, ensure_show_tables
from .serializers import (
    ScreenLayoutSerializer,
    ScreenSerializer,
    SeatSerializer,
    ShowPriceConfigurationSerializer,
    ShowSeatListSerializer,
    ShowSeatPriceSerializer,
    ShowSerializer,
    CustomerShowSerializer,
)


def cinema_for_user(user):
    if user.role != User.Role.TENANT_ADMIN or user.is_superuser:
        raise PermissionDenied("Only tenant admins can manage screens, seats, and shows.")
    cinema = Cinema.objects.filter(owner=user).first()
    if cinema is None:
        raise PermissionDenied("Your account is not assigned to a cinema.")
    return cinema


def prepare_tenant_schema(cinema):
    ensure_movie_table(cinema.schema_name)


def prepare_show_schema(cinema):
    prepare_tenant_schema(cinema)
    ensure_show_tables(cinema.schema_name)


class TenantSchemaViewMixin:
    def prepare_tenant(self, request):
        self.cinema = cinema_for_user(request.user)
        prepare_tenant_schema(self.cinema)
        return self.cinema

    def prepare_show(self, request):
        self.cinema = cinema_for_user(request.user)
        prepare_show_schema(self.cinema)
        return self.cinema


class ScreenListCreateView(TenantSchemaViewMixin, generics.ListCreateAPIView):
    serializer_class = ScreenSerializer
    permission_classes = [ScreenListCreatePermission]

    def list(self, request, *args, **kwargs):
        self.prepare_tenant(request)
        with cinema_schema(self.cinema.schema_name):
            return Response(self.get_serializer(self.get_queryset(), many=True).data)

    def create(self, request, *args, **kwargs):
        self.prepare_tenant(request)
        with cinema_schema(self.cinema.schema_name):
            serializer = self.get_serializer(
                data=request.data,
                context={"request": request, "cinema": self.cinema},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(cinema=self.cinema)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        return Screen.objects.select_related("cinema").filter(
            cinema_id=self.cinema.pk
        )


class ScreenDetailView(TenantSchemaViewMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ScreenSerializer
    permission_classes = [ScreenObjectPermission]

    def _run_in_tenant_schema(self, request, handler, *args, **kwargs):
        self.prepare_tenant(request)
        with cinema_schema(self.cinema.schema_name):
            return handler(request, *args, **kwargs)

    def get_queryset(self):
        return Screen.objects.select_related("cinema").filter(
            cinema_id=self.cinema.pk
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if hasattr(self, "cinema"):
            context["cinema"] = self.cinema
        return context

    def get(self, request, *args, **kwargs):
        return self._run_in_tenant_schema(request, super().get, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self._run_in_tenant_schema(request, super().put, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self._run_in_tenant_schema(request, super().patch, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        try:
            return self._run_in_tenant_schema(
                request,
                super().delete,
                *args,
                **kwargs,
            )
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "This screen cannot be deleted because its seats are "
                        "referenced by booking history."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )


class ScreenLayoutView(APIView):
    permission_classes = [ScreenObjectPermission]

    def post(self, request, pk):
        cinema = cinema_for_user(request.user)
        prepare_tenant_schema(cinema)
        with cinema_schema(cinema.schema_name), transaction.atomic():
            screen = Screen.objects.filter(pk=pk, cinema_id=cinema.pk).first()
            if screen is None:
                raise NotFound("Screen not found.")
            if screen.seats.exists():
                return Response(
                    {
                        "detail": (
                            "This screen's permanent seat layout has already "
                            "been configured."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            serializer = ScreenLayoutSerializer(
                data=request.data,
                context={"screen": screen},
            )
            serializer.is_valid(raise_exception=True)
            generated_seats = []
            for row in serializer.validated_data["rows"]:
                position = 1
                gaps_after = set(row["gaps_after"])
                for seat_number in range(1, row["seat_count"] + 1):
                    generated_seats.append(
                        Seat(
                            screen=screen,
                            row=row["label"],
                            seat_number=f"{row['label']}{seat_number}",
                            position=position,
                            seat_type=row["seat_type"],
                        )
                    )
                    position += 1
                    if seat_number in gaps_after:
                        position += 1

            Seat.objects.bulk_create(generated_seats)
            return Response(
                {
                    "screen": screen.pk,
                    "seat_count": len(generated_seats),
                    "seats": SeatSerializer(generated_seats, many=True).data,
                },
                status=status.HTTP_201_CREATED,
            )


class ScreenSeatListView(TenantSchemaViewMixin, generics.ListAPIView):
    serializer_class = SeatSerializer
    permission_classes = [SeatListCreatePermission]

    def list(self, request, *args, **kwargs):
        self.prepare_tenant(request)
        with cinema_schema(self.cinema.schema_name):
            return Response(self.get_serializer(self.get_queryset(), many=True).data)

    def get_queryset(self):
        screen = Screen.objects.filter(
            pk=self.kwargs["pk"],
            cinema_id=self.cinema.pk,
        ).first()
        if screen is None:
            raise NotFound("Screen not found.")
        return Seat.objects.filter(screen=screen)


class ShowListCreateView(TenantSchemaViewMixin, generics.ListCreateAPIView):
    serializer_class = ShowSerializer
    permission_classes = [ShowListCreatePermission]

    def get_queryset(self):
        return Show.objects.filter(
            screen__cinema_id=self.cinema.pk
        ).select_related("movie", "screen")

    def list(self, request, *args, **kwargs):
        return Response(discover_customer_shows(request))

    def create(self, request, *args, **kwargs):
        self.prepare_show(request)
        with cinema_schema(self.cinema.schema_name):
            serializer = self.get_serializer(
                data=request.data,
                context={"request": request, "cinema": self.cinema},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)


class ShowDetailView(TenantSchemaViewMixin, generics.RetrieveAPIView):
    serializer_class = ShowSerializer
    permission_classes = [ScreenObjectPermission]

    def get(self, request, *args, **kwargs):
        self.prepare_show(request)
        with cinema_schema(self.cinema.schema_name):
            return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return Show.objects.filter(
            screen__cinema_id=self.cinema.pk
        ).select_related("movie", "screen")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if hasattr(self, "cinema"):
            context["cinema"] = self.cinema
        return context


class CustomerShowDiscoveryView(APIView):
    permission_classes = [ShowListCreatePermission]

    def get(self, request):
        return Response(discover_customer_shows(request))


def discover_customer_shows(request):
    cinema_slug = request.query_params.get("cinema_slug")
    movie_id_value = request.query_params.get("movie_id")
    date_value = request.query_params.get("date")
    show_date = parse_date(date_value) if date_value else timezone.localdate()

    if show_date is None:
        raise ValidationError({"date": "Use the YYYY-MM-DD date format."})
    if show_date < timezone.localdate():
        raise ValidationError({"date": "Choose today or a future date."})

    movie_id = None
    if movie_id_value:
        try:
            movie_id = int(movie_id_value)
        except ValueError as error:
            raise ValidationError(
                {"movie_id": "A valid movie ID is required."}
            ) from error
        if movie_id < 1:
            raise ValidationError({"movie_id": "A valid movie ID is required."})

    cinemas = Cinema.objects.filter(status=Cinema.Status.ACTIVE).order_by("name")
    if cinema_slug:
        cinemas = cinemas.filter(slug=cinema_slug)
        if not cinemas.exists():
            raise NotFound("Active cinema not found.")

    results = []
    for cinema in cinemas:
        if not movie_table_exists(cinema.schema_name):
            continue
        prepare_show_schema(cinema)
        with cinema_schema(cinema.schema_name):
            shows = (
                Show.objects.filter(
                    screen__cinema_id=cinema.pk,
                    show_date=show_date,
                    movie__status=Movie.Status.ACTIVE,
                )
                .select_related("movie", "screen", "screen__cinema")
                .prefetch_related("seat_prices")
                .order_by("start_time", "screen_id")
            )
            if movie_id is not None:
                shows = shows.filter(movie_id=movie_id)
            if show_date == timezone.localdate():
                shows = shows.filter(
                    start_time__gt=timezone.localtime().time().replace(
                        tzinfo=None
                    )
                )

            for show in shows:
                seats = list(show.screen.seats.all())
                if not seats:
                    continue
                prices = dict(show.seat_prices.values_list("seat_type", "price"))
                seat_types = {seat.seat_type for seat in seats}
                if seat_types != set(prices):
                    continue

                with transaction.atomic():
                    show = Show.objects.select_for_update().get(pk=show.pk)
                    expire_holds_for_show(show)
                    statuses = seat_statuses_for_show(show)
                    available_count = sum(
                        1
                        for seat in seats
                        if statuses.get(seat.pk, "AVAILABLE") == "AVAILABLE"
                    )
                results.append(
                    CustomerShowSerializer(
                        {
                            "id": show.pk,
                            "screen": show.screen,
                            "movie": show.movie,
                            "show_date": show.show_date,
                            "start_time": show.start_time,
                            "end_time": show.end_time,
                            "seats_available": available_count,
                            "prices": {
                                seat_type: str(price)
                                for seat_type, price in prices.items()
                            },
                        },
                        context={"request": request},
                    ).data
                )
    return results


class ShowSeatPriceView(TenantSchemaViewMixin, APIView):
    permission_classes = [ScreenObjectPermission]

    def _get_show(self, show_id):
        show = Show.objects.filter(
            pk=show_id,
            screen__cinema_id=self.cinema.pk,
        ).select_related("screen", "movie").first()
        if show is None:
            raise NotFound("Show not found.")
        return show

    def get(self, request, show_id):
        self.prepare_show(request)
        with cinema_schema(self.cinema.schema_name):
            show = self._get_show(show_id)
            return Response(
                ShowSeatPriceSerializer(show.seat_prices.all(), many=True).data
            )

    def put(self, request, show_id):
        self.prepare_show(request)
        with cinema_schema(self.cinema.schema_name), transaction.atomic():
            show = self._get_show(show_id)
            serializer = ShowPriceConfigurationSerializer(
                data=request.data,
                context={"show": show},
            )
            serializer.is_valid(raise_exception=True)
            prices = serializer.validated_data["prices"]
            ShowSeatPrice.objects.filter(show=show).delete()
            ShowSeatPrice.objects.bulk_create(
                [
                    ShowSeatPrice(
                        show=show,
                        seat_type=item["seat_type"],
                        price=item["price"],
                    )
                    for item in prices
                ]
            )
            return Response(
                ShowSeatPriceSerializer(show.seat_prices.all(), many=True).data
            )


class ShowSeatListView(TenantSchemaViewMixin, generics.ListAPIView):
    serializer_class = ShowSeatListSerializer
    permission_classes = [ShowSeatAvailabilityPermission]

    def list(self, request, *args, **kwargs):
        if request.user.role == User.Role.TENANT_ADMIN and not request.user.is_superuser:
            cinema = cinema_for_user(request.user)
        elif request.user.role == User.Role.USER and not request.user.is_superuser:
            cinema_slug = request.query_params.get("cinema_slug")
            if not cinema_slug:
                raise ValidationError(
                    {"cinema_slug": "This query parameter is required."}
                )
            cinema = Cinema.objects.filter(
                slug=cinema_slug,
                status=Cinema.Status.ACTIVE,
            ).first()
            if cinema is None:
                raise NotFound("Active cinema not found.")
        else:
            raise PermissionDenied("Only customers and tenant admins can view seats.")

        self.cinema = cinema
        prepare_show_schema(cinema)
        with cinema_schema(cinema.schema_name), transaction.atomic():
            show = Show.objects.filter(
                pk=self.kwargs["show_id"],
                screen__cinema_id=cinema.pk,
            ).select_related("screen", "movie").first()
            if show is None:
                raise NotFound("Show not found.")
            show = Show.objects.select_for_update().get(pk=show.pk)
            expire_holds_for_show(show)
            if request.user.role == User.Role.USER and (
                cinema.status != Cinema.Status.ACTIVE
                or show.movie.status != show.movie.Status.ACTIVE
            ):
                raise NotFound("Show not found.")
            show_prices = dict(show.seat_prices.values_list("seat_type", "price"))
            seats = list(show.screen.seats.all())
            serializer = self.get_serializer(
                seats,
                many=True,
                context={
                    "show_prices": show_prices,
                    "seat_statuses": seat_statuses_for_show(show),
                },
            )
            return Response(serializer.data)
