from django.db.models.signals import pre_delete
from django.dispatch import receiver

from cinema.models import Cinema

from .models import Movie
from .schema import cinema_schema, movie_table_exists


@receiver(pre_delete, sender=Cinema)
def delete_cinema_movies(sender, instance, using, **kwargs):
    if not movie_table_exists(instance.schema_name):
        return

    with cinema_schema(instance.schema_name):
        Movie.objects.using(using).filter(cinema_id=instance.pk).delete()
