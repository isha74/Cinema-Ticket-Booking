from django.db import migrations, models
import django.db.models.deletion


def set_search_path(connection, schema_name):
    quoted_schema = connection.ops.quote_name(schema_name)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('search_path', %s, false)",
            [f"{quoted_schema}, public"],
        )


def table_exists(connection, schema_name, table_name):
    quoted_schema = connection.ops.quote_name(schema_name)
    quoted_table = connection.ops.quote_name(table_name)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass(%s)",
            [f"{quoted_schema}.{quoted_table}"],
        )
        return cursor.fetchone()[0] is not None


def reset_sequence(connection, schema_name, table_name):
    quoted_schema = connection.ops.quote_name(schema_name)
    quoted_table = connection.ops.quote_name(table_name)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT setval("
            "pg_get_serial_sequence(%s, 'id'), "
            f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL"
            f") FROM {quoted_schema}.{quoted_table}",
            [f"{schema_name}.{table_name}"],
        )


def flush_deferred_constraints(connection):
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute("SET CONSTRAINTS ALL DEFERRED")


def set_cinema_foreign_key_delete_action(connection, schema_name, delete_action):
    quoted_schema = connection.ops.quote_name(schema_name)
    quoted_table = connection.ops.quote_name("shows_screen")
    qualified_table = f"{quoted_schema}.{quoted_table}"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = %s::regclass "
            "AND confrelid = %s::regclass AND contype = 'f'",
            [f"{schema_name}.shows_screen", "public.cinema_cinema"],
        )
        constraint_names = [row[0] for row in cursor.fetchall()]
        for constraint_name in constraint_names:
            cursor.execute(
                f"ALTER TABLE {qualified_table} "
                f"DROP CONSTRAINT {connection.ops.quote_name(constraint_name)}"
            )
        cursor.execute(
            f"ALTER TABLE {qualified_table} "
            "ADD CONSTRAINT shows_screen_cinema_schema_fk "
            "FOREIGN KEY (cinema_id) "
            "REFERENCES public.cinema_cinema (id) "
            f"ON DELETE {delete_action} DEFERRABLE INITIALLY DEFERRED"
        )


def forwards(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    Screen = apps.get_model("shows", "Screen")
    Seat = apps.get_model("shows", "Seat")
    Cinema = apps.get_model("cinema", "Cinema")

    screens = list(
        Screen.objects.using(connection.alias).values(
            "id",
            "cinema_id",
            "name",
            "total_seats",
            "created_at",
        )
    )
    seats = list(
        Seat.objects.using(connection.alias).values(
            "id",
            "screen_id",
            "seat_number",
            "row",
            "seat_type",
        )
    )

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('search_path')")
        original_search_path = cursor.fetchone()[0]

    try:
        cinemas = list(Cinema.objects.using(connection.alias).all())
        for cinema in cinemas:
            quoted_schema = connection.ops.quote_name(cinema.schema_name)
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")

            set_search_path(connection, cinema.schema_name)
            with connection.schema_editor() as per_cinema_editor:
                if not table_exists(connection, cinema.schema_name, "shows_screen"):
                    per_cinema_editor.create_model(Screen)
                if not table_exists(connection, cinema.schema_name, "shows_seat"):
                    per_cinema_editor.create_model(Seat)

            cinema_screens = [
                Screen(
                    id=screen["id"],
                    cinema_id=screen["cinema_id"],
                    name=screen["name"],
                    total_seats=screen["total_seats"],
                    created_at=screen["created_at"],
                )
                for screen in screens
                if screen["cinema_id"] == cinema.pk
            ]
            if cinema_screens:
                Screen.objects.using(connection.alias).bulk_create(cinema_screens)

            cinema_screen_ids = {screen.pk for screen in cinema_screens}
            cinema_seats = [
                Seat(
                    id=seat["id"],
                    screen_id=seat["screen_id"],
                    seat_number=seat["seat_number"],
                    row=seat["row"],
                    seat_type=seat["seat_type"],
                )
                for seat in seats
                if seat["screen_id"] in cinema_screen_ids
            ]
            if cinema_seats:
                Seat.objects.using(connection.alias).bulk_create(cinema_seats)

            reset_sequence(connection, cinema.schema_name, "shows_screen")
            reset_sequence(connection, cinema.schema_name, "shows_seat")
            flush_deferred_constraints(connection)
            set_cinema_foreign_key_delete_action(
                connection,
                cinema.schema_name,
                "NO ACTION",
            )

        set_search_path(connection, "public")
        flush_deferred_constraints(connection)
        with connection.schema_editor() as public_editor:
            public_editor.delete_model(Seat)
            public_editor.delete_model(Screen)
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('search_path', %s, false)",
                [original_search_path],
            )


def backwards(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    Screen = apps.get_model("shows", "Screen")
    Seat = apps.get_model("shows", "Seat")
    Cinema = apps.get_model("cinema", "Cinema")
    cinema_rows = []

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('search_path')")
        original_search_path = cursor.fetchone()[0]

    try:
        cinemas = list(Cinema.objects.using(connection.alias).all())
        for cinema in cinemas:
            if not table_exists(connection, cinema.schema_name, "shows_screen"):
                continue
            set_search_path(connection, cinema.schema_name)
            cinema_rows.append(
                (
                    cinema.schema_name,
                    list(Screen.objects.using(connection.alias).values()),
                    list(Seat.objects.using(connection.alias).values()),
                )
            )

        set_search_path(connection, "public")
        with connection.schema_editor() as public_editor:
            public_editor.create_model(Screen)
            public_editor.create_model(Seat)

        screen_ids = set()
        screen_id_map = {}
        for schema_name, screens, _ in cinema_rows:
            for screen in screens:
                screen_id = screen["id"]
                screen_data = {
                    "cinema_id": screen["cinema_id"],
                    "name": screen["name"],
                    "total_seats": screen["total_seats"],
                    "created_at": screen["created_at"],
                }
                if screen_id in screen_ids:
                    restored = Screen.objects.using(connection.alias).create(
                        **screen_data
                    )
                else:
                    restored = Screen.objects.using(connection.alias).create(
                        id=screen_id,
                        **screen_data,
                    )
                screen_ids.add(restored.pk)
                screen_id_map[(schema_name, screen_id)] = restored.pk

        seat_ids = set()
        for schema_name, _, seats in cinema_rows:
            for seat in seats:
                seat_data = {
                    "screen_id": screen_id_map[(schema_name, seat["screen_id"])],
                    "seat_number": seat["seat_number"],
                    "row": seat["row"],
                    "seat_type": seat["seat_type"],
                }
                if seat["id"] in seat_ids:
                    restored = Seat.objects.using(connection.alias).create(
                        **seat_data
                    )
                else:
                    restored = Seat.objects.using(connection.alias).create(
                        id=seat["id"],
                        **seat_data,
                    )
                seat_ids.add(restored.pk)

        reset_sequence(connection, "public", "shows_screen")
        reset_sequence(connection, "public", "shows_seat")
        flush_deferred_constraints(connection)
        set_cinema_foreign_key_delete_action(connection, "public", "CASCADE")

        cinemas = list(Cinema.objects.using(connection.alias).all())
        flush_deferred_constraints(connection)
        for cinema in cinemas:
            if not table_exists(connection, cinema.schema_name, "shows_screen"):
                continue
            set_search_path(connection, cinema.schema_name)
            with connection.schema_editor() as per_cinema_editor:
                per_cinema_editor.delete_model(Seat)
                per_cinema_editor.delete_model(Screen)
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('search_path', %s, false)",
                [original_search_path],
            )


class Migration(migrations.Migration):
    dependencies = [
        ("shows", "0001_initial"),
        ("cinema", "0003_remove_tenant_schema_prefix"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(forwards, backwards),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="screen",
                    name="cinema",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="screens",
                        to="cinema.cinema",
                    ),
                ),
            ],
        ),
    ]
