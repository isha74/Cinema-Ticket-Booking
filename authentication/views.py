from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from cinema.models import Cinema

from .models import User
from .permissions import IsNormalUser, IsSuperAdmin, IsTenantAdmin
from .serializers import TenantRegistrationSerializer, UserRegistrationSerializer

class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer


class TenantRegistrationView(generics.CreateAPIView):
    serializer_class = TenantRegistrationSerializer
    permission_classes = [IsSuperAdmin]


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = User.Role.SUPER_ADMIN if user.is_superuser else user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        if user.role == User.Role.TENANT_ADMIN and not user.is_superuser:
            try:
                cinema_status = user.cinema.status
            except Cinema.DoesNotExist:
                raise AuthenticationFailed(
                    "Your account is not assigned to a cinema."
                )

            if cinema_status == Cinema.Status.PENDING:
                raise AuthenticationFailed(
                    "Your cinema registration is awaiting admin approval."
                )
            if cinema_status != Cinema.Status.ACTIVE:
                raise AuthenticationFailed(
                    "Your cinema registration was rejected. Contact the administrator."
                )

        return data


class LoginView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "role": User.Role.SUPER_ADMIN if request.user.is_superuser else request.user.role,
        })


class UserDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": User.Role.SUPER_ADMIN if user.is_superuser else user.role,
        })


class SuperAdminTestView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        return Response({
            "message": "Welcome Super Admin"
        })


class TenantAdminTestView(APIView):
    permission_classes = [IsTenantAdmin]

    def get(self, request):
        return Response({
            "message": "Welcome Tenant Admin"
        })


class UserTestView(APIView):
    permission_classes = [IsNormalUser]

    def get(self, request):
        return Response({
            "message": "Welcome User"
        })
