from django.db import connection

from cinema.schema import cinema_schema


def ensure_booking_tables(schema_name):
    if connection.vendor == "postgresql":
        quoted_schema = connection.ops.quote_name(schema_name)
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS " + quoted_schema)
            cursor.execute(
                "SELECT to_regclass(%s), to_regclass(%s)",
                [
                    f"{quoted_schema}.bookings_booking",
                    f"{quoted_schema}.bookings_bookingseat",
                ],
            )
            booking_exists, seat_exists = cursor.fetchone()
    else:
        names = set(connection.introspection.table_names())
        booking_exists = "bookings_booking" in names
        seat_exists = "bookings_bookingseat" in names

    if seat_exists and not booking_exists:
        raise RuntimeError(
            f"Cannot initialize schema '{schema_name}': "
            "bookings_bookingseat exists without bookings_booking."
        )
    if booking_exists and seat_exists:
        return

    from .models import Booking, BookingSeat

    with cinema_schema(schema_name):
        with connection.schema_editor() as schema_editor:
            if not booking_exists:
                schema_editor.create_model(Booking)
            if not seat_exists:
                schema_editor.create_model(BookingSeat)
