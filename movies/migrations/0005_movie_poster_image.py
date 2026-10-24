import movies.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("movies", "0004_movie_cinema_do_nothing_on_delete"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="movie",
                    name="poster",
                    field=models.ImageField(
                        blank=True,
                        null=True,
                        upload_to=movies.models.movie_poster_upload_path,
                    ),
                ),
            ],
        ),
    ]
