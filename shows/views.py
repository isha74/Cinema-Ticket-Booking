from django.db import connection
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from authentication.models import User
from cinema.models import Cinema
from cinema.permissions import is_super_admin

from .models import Screen
from .permissions import ScreenListCreatePermission, ScreenObjectPermission
from .schema import cinema_schema, ensure_screen_tables
from .serializers import ScreenSerializer


def visible_cinemas_for(user):
    cinemas = Cinema.objects.select_related("owner")
    if is_super_admin(user):
        return cinemas
    if user.role == User.Role.TENANT_ADMIN:
        return cinemas.filter(owner=user)
    if user.role == User.Role.USER:
        return cinemas.filter(status=Cinema.Status.ACTIVE)
    return cinemas.none()


def cinema_for_schema_request(request, *, required):
    schema_name = request.headers.get("X-Schema-Name")
    if not schema_name:
        if required:
            raise ValidationError(
                {"X-Schema-Name": "This header is required for screen requests."}
            )
        return None

    cinema = visible_cinemas_for(request.user).filter(
        schema_name=schema_name
    ).first()
    if cinema is None:
        raise PermissionDenied(
            "The X-Schema-Name header does not identify a cinema you can access."
        )
    return cinema


class ScreenListCreateView(generics.ListCreateAPIView):
    serializer_class = ScreenSerializer
    permission_classes = [ScreenListCreatePermission]

    def list(self, request, *args, **kwargs):
        selected_cinema = cinema_for_schema_request(
            request,
            required=request.user.role == User.Role.TENANT_ADMIN,
        )
        cinemas = (
            [selected_cinema]
            if selected_cinema is not None
            else list(visible_cinemas_for(request.user))
        )

        if connection.vendor != "postgresql":
            screens = Screen.objects.select_related(
                "cinema",
                "cinema__owner",
            ).filter(cinema_id__in=[cinema.pk for cinema in cinemas])
            return Response(self.get_serializer(screens, many=True).data)

        data = []
        for cinema in cinemas:
            ensure_screen_tables(cinema.schema_name)
            with cinema_schema(cinema.schema_name):
                screens = Screen.objects.select_related(
                    "cinema",
                    "cinema__owner",
                ).filter(cinema_id=cinema.pk)
                data.extend(self.get_serializer(screens, many=True).data)
        data.sort(key=lambda screen: (screen["cinema_name"], screen["name"]))
        return Response(data)

    def create(self, request, *args, **kwargs):
        cinema = cinema_for_schema_request(request, required=True)
        self.cinema = cinema
        ensure_screen_tables(cinema.schema_name)
        with cinema_schema(cinema.schema_name):
            return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        if self.cinema is None:
            raise PermissionDenied("Your account is not assigned to a cinema.")
        serializer.save(cinema=self.cinema)


class ScreenDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ScreenSerializer
    permission_classes = [ScreenObjectPermission]

    def get_queryset(self):
        return Screen.objects.select_related(
            "cinema",
            "cinema__owner",
        ).filter(cinema_id=self.cinema.pk)

    def _prepare_schema(self, request):
        self.cinema = cinema_for_schema_request(request, required=True)
        ensure_screen_tables(self.cinema.schema_name)

    def get(self, request, *args, **kwargs):
        self._prepare_schema(request)
        with cinema_schema(self.cinema.schema_name):
            return super().get(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        self._prepare_schema(request)
        with cinema_schema(self.cinema.schema_name):
            return super().put(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        self._prepare_schema(request)
        with cinema_schema(self.cinema.schema_name):
            return super().patch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        self._prepare_schema(request)
        with cinema_schema(self.cinema.schema_name):
            return super().delete(request, *args, **kwargs)
