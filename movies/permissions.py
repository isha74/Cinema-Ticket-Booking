from rest_framework.permissions import SAFE_METHODS, BasePermission

from authentication.models import User
from cinema.models import Cinema

from .models import Movie


class MovieListCreatePermission(BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            return (
                request.user.is_authenticated
                and request.user.role == User.Role.TENANT_ADMIN
            )
        return request.user.is_authenticated


class MovieObjectPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return (
                user.is_superuser
                or user.role in (
                    User.Role.SUPER_ADMIN,
                    User.Role.TENANT_ADMIN,
                    User.Role.USER,
                )
            )
        return user.role == User.Role.TENANT_ADMIN

    def has_object_permission(self, request, view, obj):
        user = request.user

        if not user.is_authenticated:
            return False

        if user.role == User.Role.TENANT_ADMIN:
            return obj.cinema.owner_id == user.id

        if user.is_superuser or user.role == User.Role.SUPER_ADMIN:
            return request.method in SAFE_METHODS

        if request.method in SAFE_METHODS and user.role == User.Role.USER:
            return (
                obj.status == Movie.Status.ACTIVE
                and obj.cinema.status == Cinema.Status.ACTIVE
            )

        return False
