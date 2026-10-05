from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields["role"] = "SUPER_ADMIN"
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):

    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        TENANT_ADMIN = "TENANT_ADMIN", "Tenant Admin"
        USER = "USER", "User"

    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER
    )

    objects = UserManager()

    def __str__(self):
        return f"{self.username} - {self.role}"