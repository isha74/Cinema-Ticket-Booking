import re

from django.db import migrations


def schema_name_from_domain(domain):
    return (re.sub(r"[^a-z0-9]+", "_", domain.lower()).strip("_") or "cinema")[:63].rstrip("_")


def remove_tenant_schema_prefix(apps, schema_editor):
    Cinema = apps.get_model("cinema", "Cinema")
    connection = schema_editor.connection

    for cinema in Cinema.objects.all():
        new_schema_name = schema_name_from_domain(cinema.domain)
        if cinema.schema_name == new_schema_name:
            continue

        base_schema_name = new_schema_name
        counter = 1
        while Cinema.objects.exclude(pk=cinema.pk).filter(schema_name=new_schema_name).exists():
            counter += 1
            suffix = f"_{counter}"
            new_schema_name = f"{base_schema_name[:63 - len(suffix)]}{suffix}"

        if connection.vendor == "postgresql":
            old_name = connection.ops.quote_name(cinema.schema_name)
            new_name = connection.ops.quote_name(new_schema_name)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                    [cinema.schema_name],
                )
                old_schema_exists = cursor.fetchone()[0]
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                    [new_schema_name],
                )
                new_schema_exists = cursor.fetchone()[0]

                if old_schema_exists and not new_schema_exists:
                    cursor.execute(f"ALTER SCHEMA {old_name} RENAME TO {new_name}")
                elif not new_schema_exists:
                    cursor.execute(f"CREATE SCHEMA {new_name}")

        cinema.schema_name = new_schema_name
        cinema.save(update_fields=["schema_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("cinema", "0002_cinema_domain_schema_status"),
    ]

    operations = [
        migrations.RunPython(remove_tenant_schema_prefix, migrations.RunPython.noop),
    ]
