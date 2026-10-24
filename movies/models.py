from pathlib import Path
from uuid import uuid4

from django.db import models

from cinema.models import Cinema


def movie_poster_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"movie-posters/{instance.cinema_id}/{uuid4().hex}{extension}"


class Movie(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    cinema = models.ForeignKey(
        Cinema,
        on_delete=models.DO_NOTHING,
        related_name="movies",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    duration = models.PositiveSmallIntegerField(help_text="Duration in minutes")
    language = models.CharField(max_length=100)
    genre = models.CharField(max_length=100)
    release_date = models.DateField()
    poster = models.ImageField(
        upload_to=movie_poster_upload_path,
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "id"]

    def __str__(self):
        return f"{self.title} ({self.cinema.name})"
