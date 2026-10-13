from django.db import connection

from cinema.schema import cinema_schema


def ensure_screen_tables(schema_name):
    if connection.vendor != "postgresql":
        return

    quoted_schema = connection.ops.quote_name(schema_name)
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")
        cursor.execute(
            "SELECT to_regclass(%s), to_regclass(%s)",
            [
                f"{quoted_schema}.shows_screen",
                f"{quoted_schema}.shows_seat",
            ],
        )
        screen_exists, seat_exists = cursor.fetchone()

    if screen_exists and seat_exists:
        return
    if seat_exists and not screen_exists:
        raise RuntimeError(
            f"Cannot initialize schema '{schema_name}': shows_seat exists "
            "without shows_screen."
        )

    from .models import Screen, Seat

    with cinema_schema(schema_name):
        with connection.schema_editor() as schema_editor:
            if not screen_exists:
                schema_editor.create_model(Screen)
            if not seat_exists:
                schema_editor.create_model(Seat)
