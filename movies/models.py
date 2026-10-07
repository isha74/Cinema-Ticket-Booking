from django.db import models

from cinema.models import Cinema


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
