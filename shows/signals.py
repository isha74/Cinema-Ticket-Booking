from django.db.models.signals import pre_delete
from django.dispatch import receiver

from cinema.models import Cinema
from cinema.schema import cinema_schema

from .models import Screen
from .schema import ensure_screen_tables


@receiver(pre_delete, sender=Cinema)
def delete_cinema_screens(sender, instance, using, **kwargs):
    ensure_screen_tables(instance.schema_name)
    with cinema_schema(instance.schema_name):
        Screen.objects.using(using).filter(cinema_id=instance.pk).delete()
