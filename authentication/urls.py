from django.urls import path

from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from .views import (
    LoginView,
    MeView,
    SuperAdminTestView,
    TenantAdminTestView,
    TenantRegistrationView,
    UserDetailView,
    UserRegistrationView,
    UserTestView,
)

urlpatterns = [
    path("register/", UserRegistrationView.as_view(), name="user-register"),
    path("register/tenant/", TenantRegistrationView.as_view(), name="tenant-register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="current-user"),

    path("<int:user_id>/", UserDetailView.as_view(), name="user-detail"),

    path("test/super-admin/", SuperAdminTestView.as_view()),
    path("test/tenant-admin/", TenantAdminTestView.as_view()),
    path("test/user/", UserTestView.as_view()),
]