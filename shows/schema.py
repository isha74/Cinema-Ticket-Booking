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
            else:
                with connection.cursor() as cursor:
                    columns = {
                        column.name
                        for column in connection.introspection.get_table_description(
                            cursor,
                            Seat._meta.db_table,
                        )
                    }
                if "position" not in columns:
                    schema_editor.add_field(
                        Seat,
                        Seat._meta.get_field("position"),
                    )


def ensure_show_tables(schema_name):
    if connection.vendor != "postgresql":
        return

    quote = connection.ops.quote_name
    quoted_schema = quote(schema_name)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass(%s), to_regclass(%s)",
            [
                f"{quoted_schema}.shows_show",
                f"{quoted_schema}.shows_showseatprice",
            ],
        )
        show_exists, price_exists = cursor.fetchone()
    if show_exists and price_exists:
        return

    from .models import Show, ShowSeatPrice

    with cinema_schema(schema_name):
        with connection.schema_editor() as schema_editor:
            if not show_exists:
                schema_editor.create_model(Show)
            if not price_exists:
                schema_editor.create_model(ShowSeatPrice)
