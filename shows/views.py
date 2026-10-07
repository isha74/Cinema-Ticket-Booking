from rest_framework import generics
from rest_framework.exceptions import PermissionDenied

from authentication.models import User
from cinema.models import Cinema
from cinema.permissions import is_super_admin

from .models import Screen
from .permissions import ScreenListCreatePermission, ScreenObjectPermission
from .serializers import ScreenSerializer


class ScreenListCreateView(generics.ListCreateAPIView):
    serializer_class = ScreenSerializer
    permission_classes = [ScreenListCreatePermission]

    def get_queryset(self):
        user = self.request.user
        queryset = Screen.objects.select_related("cinema", "cinema__owner")

        if is_super_admin(user):
            return queryset
        if user.role == User.Role.TENANT_ADMIN:
            return queryset.filter(cinema__owner=user)
        if user.role == User.Role.USER:
            return queryset.filter(cinema__status=Cinema.Status.ACTIVE)
        return queryset.none()

    def perform_create(self, serializer):
        cinema = Cinema.objects.filter(owner=self.request.user).first()
        if cinema is None:
            raise PermissionDenied("Your account is not assigned to a cinema.")
        serializer.save(cinema=cinema)


class ScreenDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Screen.objects.select_related("cinema", "cinema__owner")
    serializer_class = ScreenSerializer
    permission_classes = [ScreenObjectPermission]
