from contextlib import contextmanager

from django.db import connection


@contextmanager
def cinema_schema(schema_name):
    if connection.vendor != "postgresql":
        yield
        return

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('search_path')")
        original_search_path = cursor.fetchone()[0]
        cursor.execute(
            "SELECT set_config('search_path', %s, false)",
            [f"{connection.ops.quote_name(schema_name)}, public"],
        )

    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('search_path', %s, false)",
                [original_search_path],
            )
