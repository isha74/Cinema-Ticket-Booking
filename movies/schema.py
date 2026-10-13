from django.db import connection

from cinema.schema import cinema_schema


def ensure_movie_table(schema_name):
    table_exists = movie_table_exists(schema_name)

    if table_exists:
        return

    from .models import Movie

    with cinema_schema(schema_name):
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(Movie)


def movie_table_exists(schema_name):
    if connection.vendor == "postgresql":
        quoted_schema = connection.ops.quote_name(schema_name)
        quoted_table = connection.ops.quote_name("movies_movie")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass(%s)",
                [f"{quoted_schema}.{quoted_table}"],
            )
            return cursor.fetchone()[0] is not None

    return "movies_movie" in connection.introspection.table_names()


def allocate_movie_id():
    if connection.vendor != "postgresql":
        return None

    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('public.movie_global_id_seq')")
        return cursor.fetchone()[0]
