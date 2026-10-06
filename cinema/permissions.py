from rest_framework.permissions import SAFE_METHODS, BasePermission

from authentication.models import User

from .models import Cinema


def is_super_admin(user):
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.role == User.Role.SUPER_ADMIN
        )
    )


class CinemaListCreatePermission(BasePermission):
    def has_permission(self, request, view):
        if request.method == "POST":
            return is_super_admin(request.user)
        return request.user.is_authenticated


class CinemaObjectPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user

        if is_super_admin(user):
            return True

        if request.method in SAFE_METHODS:
            if user.role == User.Role.TENANT_ADMIN:
                return obj.owner_id == user.id
            if user.role == User.Role.USER:
                return obj.status == Cinema.Status.ACTIVE
            return False

        if request.method in ("PUT", "PATCH"):
            return user.role == User.Role.TENANT_ADMIN and obj.owner_id == user.id

        return False
