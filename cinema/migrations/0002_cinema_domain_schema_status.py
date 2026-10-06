from django.db import migrations, models
from django.utils.text import slugify


def populate_tenant_fields(apps, schema_editor):
    Cinema = apps.get_model("cinema", "Cinema")

    for cinema in Cinema.objects.all():
        base_slug = slugify(cinema.name) or f"cinema-{cinema.pk}"
        domain = f"{base_slug}.local"
        schema_name = base_slug.replace("-", "_")[:63].rstrip("_")

        domain_counter = 1
        unique_domain = domain
        while Cinema.objects.exclude(pk=cinema.pk).filter(domain=unique_domain).exists():
            domain_counter += 1
            unique_domain = f"{base_slug}-{domain_counter}.local"

        schema_counter = 1
        unique_schema_name = schema_name
        while Cinema.objects.exclude(pk=cinema.pk).filter(schema_name=unique_schema_name).exists():
            schema_counter += 1
            suffix = f"_{schema_counter}"
            unique_schema_name = f"{schema_name[:63 - len(suffix)]}{suffix}"

        cinema.domain = unique_domain
        cinema.schema_name = unique_schema_name
        cinema.status = "PENDING"
        cinema.save(update_fields=["domain", "schema_name", "status"])


class Migration(migrations.Migration):

    dependencies = [
        ("cinema", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cinema",
            name="domain",
            field=models.CharField(max_length=253, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="cinema",
            name="schema_name",
            field=models.CharField(max_length=63, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="cinema",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("ACTIVE", "Active"),
                    ("REJECTED", "Rejected"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
        migrations.RunPython(populate_tenant_fields, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="cinema",
            name="domain",
            field=models.CharField(max_length=253, unique=True),
        ),
        migrations.AlterField(
            model_name="cinema",
            name="schema_name",
            field=models.CharField(max_length=63, unique=True),
        ),
    ]
