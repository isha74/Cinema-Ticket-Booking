from django.db.models.deletion import ProtectedError
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from authentication.permissions import IsSuperAdmin
from movies.schema import ensure_movie_table
from .models import Cinema
from .permissions import (
    CinemaListCreatePermission,
    CinemaObjectPermission,
    is_super_admin,
)
from .serializers import (
    CinemaRegistrationSerializer,
    CinemaSerializer,
    CinemaUpdateSerializer,
)


class BookingHistoryConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This cinema cannot be deleted while it has booking history."
    default_code = "booking_history_protected"


class CinemaRegistrationView(generics.CreateAPIView):
    queryset = Cinema.objects.select_related("owner")
    serializer_class = CinemaRegistrationSerializer
    permission_classes = [AllowAny]


class CinemaListCreateView(generics.ListCreateAPIView):
    queryset = Cinema.objects.select_related("owner")
    permission_classes = [CinemaListCreatePermission]

    def get_queryset(self):
        user = self.request.user
        queryset = Cinema.objects.select_related("owner")

        if is_super_admin(user):
            return queryset
        if not user.is_authenticated:
            return queryset.none()
        if user.role == User.Role.TENANT_ADMIN:
            return queryset.filter(owner=user)
        if user.role == User.Role.USER:
            return queryset.filter(status=Cinema.Status.ACTIVE)
        return queryset.none()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CinemaRegistrationSerializer
        return CinemaSerializer


class CinemaDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Cinema.objects.select_related("owner")
    permission_classes = [CinemaObjectPermission]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return CinemaUpdateSerializer
        return CinemaSerializer

    def perform_destroy(self, instance):
        ensure_movie_table(instance.schema_name)
        try:
            instance.delete()
        except ProtectedError as error:
            raise BookingHistoryConflict() from error


class CinemaApproveView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        cinema = generics.get_object_or_404(Cinema.objects.select_related("owner"), pk=pk)
        cinema.status = Cinema.Status.ACTIVE
        cinema.save(update_fields=["status", "updated_at"])
        return Response(CinemaSerializer(cinema).data, status=status.HTTP_200_OK)


class CinemaRejectView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        cinema = generics.get_object_or_404(Cinema.objects.select_related("owner"), pk=pk)
        cinema.status = Cinema.Status.REJECTED
        cinema.save(update_fields=["status", "updated_at"])
        return Response(CinemaSerializer(cinema).data, status=status.HTTP_200_OK)
