from rest_framework.permissions import BasePermission

from authentication.models import User


def _is_tenant_admin(user):
    return (
        user.is_authenticated
        and not user.is_superuser
        and user.role == User.Role.TENANT_ADMIN
    )


class TenantAdminOnlyPermission(BasePermission):
    def has_permission(self, request, view):
        return _is_tenant_admin(request.user)


class ScreenListCreatePermission(TenantAdminOnlyPermission):
    pass


class ScreenObjectPermission(TenantAdminOnlyPermission):
    pass


class SeatListCreatePermission(TenantAdminOnlyPermission):
    pass


class SeatObjectPermission(TenantAdminOnlyPermission):
    pass


class ShowSeatAvailabilityPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated
            and not user.is_superuser
            and user.role in (User.Role.TENANT_ADMIN, User.Role.USER)
        )


class ShowListCreatePermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated or user.is_superuser:
            return False
        if request.method == "POST":
            return user.role == User.Role.TENANT_ADMIN
        return user.role in (User.Role.TENANT_ADMIN, User.Role.USER)

