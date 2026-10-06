from django.conf import settings
from django.db import models


class Cinema(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        REJECTED = "REJECTED", "Rejected"

    name = models.CharField(max_length=255, unique=True)
    domain = models.CharField(max_length=253, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    schema_name = models.CharField(max_length=63, unique=True)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cinema",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
