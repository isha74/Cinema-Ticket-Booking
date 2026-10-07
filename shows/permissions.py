from rest_framework.permissions import SAFE_METHODS, BasePermission

from authentication.models import User
from cinema.models import Cinema
from cinema.permissions import is_super_admin


class ScreenListCreatePermission(BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            return (
                request.user.is_authenticated
                and request.user.role == User.Role.TENANT_ADMIN
            )
        return request.user.is_authenticated


class ScreenObjectPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return request.user.role in (
                User.Role.SUPER_ADMIN,
                User.Role.TENANT_ADMIN,
                User.Role.USER,
            ) or request.user.is_superuser
        return request.user.role == User.Role.TENANT_ADMIN

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == User.Role.TENANT_ADMIN:
            return obj.cinema.owner_id == user.id
        if is_super_admin(user):
            return request.method in SAFE_METHODS
        if request.method in SAFE_METHODS and user.role == User.Role.USER:
            return obj.cinema.status == Cinema.Status.ACTIVE
        return False
