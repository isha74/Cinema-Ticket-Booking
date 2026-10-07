from django.db import migrations


def set_search_path(connection, schema_name):
    quoted_schema = connection.ops.quote_name(schema_name)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('search_path', %s, false)",
            [f"{quoted_schema}, public"],
        )


def table_exists(connection, schema_name):
    quoted_schema = connection.ops.quote_name(schema_name)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass(%s)",
            [f"{quoted_schema}.movies_movie"],
        )
        return cursor.fetchone()[0] is not None


def forwards(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    Movie = apps.get_model("movies", "Movie")
    Cinema = apps.get_model("cinema", "Cinema")
    old_movies = list(Movie.objects.all().values())
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('search_path')")
        original_search_path = cursor.fetchone()[0]
        cursor.execute("CREATE SEQUENCE IF NOT EXISTS public.movie_global_id_seq")
        maximum_movie_id = max(
            (movie["id"] for movie in old_movies),
            default=0,
        )
        cursor.execute(
            "SELECT setval('public.movie_global_id_seq', %s, %s)",
            [max(maximum_movie_id, 1), maximum_movie_id > 0],
        )

    for cinema in Cinema.objects.all().iterator():
        with connection.cursor() as cursor:
            quoted_schema = connection.ops.quote_name(cinema.schema_name)
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")

        created_table = not table_exists(connection, cinema.schema_name)
        if created_table:
            set_search_path(connection, cinema.schema_name)
            with connection.schema_editor() as per_cinema_editor:
                per_cinema_editor.create_model(Movie)

        set_search_path(connection, cinema.schema_name)
        existing_ids = set(
            Movie.objects.filter(cinema_id=cinema.pk).values_list("id", flat=True)
        )
        cinema_movies = [
            Movie(
                id=movie["id"],
                cinema_id=movie["cinema_id"],
                title=movie["title"],
                description=movie["description"],
                duration=movie["duration"],
                language=movie["language"],
                genre=movie["genre"],
                release_date=movie["release_date"],
                status=movie["status"],
                created_at=movie["created_at"],
            )
            for movie in old_movies
            if movie["cinema_id"] == cinema.pk and movie["id"] not in existing_ids
        ]
        if cinema_movies:
            Movie.objects.bulk_create(cinema_movies)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT setval("
                    "pg_get_serial_sequence('movies_movie', 'id'), "
                    "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL"
                    ") FROM movies_movie"
                )

    set_search_path(connection, "public")
    with connection.schema_editor() as public_editor:
        public_editor.delete_model(Movie)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('search_path', %s, false)",
            [original_search_path],
        )


def backwards(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    Movie = apps.get_model("movies", "Movie")
    Cinema = apps.get_model("cinema", "Cinema")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('search_path')")
        old_search_path = cursor.fetchone()[0]

    set_search_path(connection, "public")
    with connection.schema_editor() as public_editor:
        public_editor.create_model(Movie)

    collected_movies = []
    for cinema in Cinema.objects.all().iterator():
        if not table_exists(connection, cinema.schema_name):
            continue
        set_search_path(connection, cinema.schema_name)
        collected_movies.extend(
            Movie.objects.all().values(
                "cinema_id",
                "title",
                "description",
                "duration",
                "language",
                "genre",
                "release_date",
                "status",
                "created_at",
            )
        )
        with connection.schema_editor() as cinema_editor:
            cinema_editor.delete_model(Movie)

    set_search_path(connection, "public")
    Movie.objects.bulk_create(
        [
            Movie(**movie)
            for movie in collected_movies
        ]
    )
    with connection.cursor() as cursor:
        cursor.execute("DROP SEQUENCE IF EXISTS public.movie_global_id_seq")
        cursor.execute(
            "SELECT set_config('search_path', %s, false)",
            [old_search_path],
        )


class Migration(migrations.Migration):
    dependencies = [
        ("movies", "0002_remove_movie_poster_remove_movie_updated_at_and_more"),
        ("cinema", "0003_remove_tenant_schema_prefix"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
